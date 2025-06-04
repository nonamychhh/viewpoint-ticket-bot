import time
import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import Message
from handlers import get_or_create_topic,config,parse_time
from load_config import load_config
from aiogram.types import User
import asyncio
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.middleware import StorageKey


DATABASE = 'data/bans.db'
CACHE_TTL = 30  # seconds

class AsyncIgnoreMiddleware(BaseMiddleware):
    def __init__(self,storage: BaseStorage):
        self.cache = {}
        self.last_cache_update = 0
        self.cache_ttl = CACHE_TTL
        self.db_path = DATABASE
        self.bot = None
        self.storage = storage
        self.timeout_task = asyncio.create_task(self.check_states_timeout())
        self.active_states = set()  # Track active states manually
        self.last_activity = {}  # Track last activity time for users
    async def update_cache(self):
        current_time = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            cursor = await db.execute(
                '''SELECT user_id, ban_end FROM ignored_users 
                WHERE ban_end > ?''',
                (current_time,)
            )
            self.cache = {row[0]: row[1] for row in await cursor.fetchall()}
            self.last_cache_update = current_time

    async def __call__(self, handler, event: Message, data):
        # Update active states when a user interacts with the bot
        user_id = event.from_user.id
        chat_id = event.chat.id
        bot_id = event.bot.id
        storage_key = StorageKey(user_id=user_id, chat_id=chat_id,bot_id=bot_id)
        self.active_states.add(storage_key)

        original_user = None
        if event.forward_from:
            original_user = event.forward_from.id
        elif event.reply_to_message and event.reply_to_message.forward_from:
            original_user = event.reply_to_message.forward_from.id
        
        user_id = original_user or event.from_user.id
        if not isinstance(event, Message):
            return await handler(event, data)
        current_time = time.time()

        if current_time - self.last_cache_update > self.cache_ttl:
            await self.update_cache()

        if user_id in self.cache:
            if current_time < self.cache[user_id]:
                return

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''SELECT ban_end FROM ignored_users 
                WHERE user_id = ?''',
                (user_id,)
            )
            result = await cursor.fetchone()
            
        if result and current_time < result[0]:
            self.cache[user_id] = result[0]
            return
        
        state: FSMContext = data.get('state')
        if state and await state.get_state() is not None:
        # Только обновляем время активности
            storage_key = StorageKey(
                bot_id=event.bot.id,
                chat_id=event.chat.id,
                user_id=user_id
            )
        self.last_activity[(user_id, event.chat.id)] = current_time
        self.bot = event.bot
        return await handler(event, data)
    
    async def check_states_timeout(self):
        """Фоновая задача для сброса устаревших состояний"""
        while True:
            interval = config.get("state_timeout_check_interval", 15)
            if interval != 15:
                interval = parse_time(interval)
            if interval <= 0:
                interval = 15
            await asyncio.sleep(interval)

            current_time = time.time()
            state_timeout = config.get("state_timeout", 1800)  # 30 минут по умолчанию
            if state_timeout != 1800:
                state_timeout = parse_time(state_timeout)

            if state_timeout <= 0:
                state_timeout = 1800

            # Итерация по отслеживаемым активным состояниям
            for storage_key in list(self.active_states):
                # Получаем время последней активности из хранилища
                data = await self.storage.get_data(storage_key)
                last_time = data.get("last_activity", 0)  # По умолчанию 0, если не найдено

                # Сбрасываем состояние, если неактивен слишком долго
                if current_time - last_time >= state_timeout:
                    state = FSMContext(storage=self.storage, key=storage_key)
                    if await state.get_state() is not None:
                        await state.set_state(None)
                        self.active_states.remove(storage_key)  # Удаляем из активных состояний

                        # Уведомляем пользователя или выполняем другие действия
                        user_info = await self.bot.get_chat(storage_key.user_id)
                        await get_or_create_topic(user_info, config["emojis"]["unbanned"]["emoji"], self.bot)

    async def close(self):
        """Остановка фоновых задач при завершении"""
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass