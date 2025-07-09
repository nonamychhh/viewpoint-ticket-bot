import time
import aiosqlite
import asyncio
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.middleware import StorageKey
from handlers import parse_time,get_or_create_topic
from load_config import load_config

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(f"logs/{__name__}.log", mode='a',encoding='utf-8')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

DATABASE = 'data/bans.db'
CACHE_TTL = 30  # seconds

class AsyncIgnoreMiddleware(BaseMiddleware):
    """Middleware для игнорирования забаненных пользователей и управления состояниями"""
    
    def __init__(self, storage: BaseStorage):
        self.cache = {}
        self.last_cache_update = 0
        self.cache_ttl = CACHE_TTL
        self.db_path = DATABASE
        self.bot = None
        self.storage = storage
        self.active_states = set()
        self.user = None
        self.timeout_task = asyncio.create_task(self.check_states_timeout())
        logger.info("Middleware инициализирован")

    @property
    def config(self):
        return load_config()
    
    async def update_cache(self):
        """Обновляет кэш забаненных пользователей"""
        try:
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
                logger.info("Кэш банов обновлен")
        except Exception as e:
            logger.error(f"Ошибка обновления кэша: {str(e)}")

    async def __call__(self, handler, event: Message, data):
        """Обрабатывает входящие сообщения"""
        try:
            if not isinstance(event, Message):
                return await handler(event, data)
                
            # Инициализация бота при первом сообщении
            if self.bot is None:
                self.bot = event.bot
                
            user_id = event.from_user.id
            current_time = time.time()

            # Обновление кэша банов
            if current_time - self.last_cache_update > self.cache_ttl:
                await self.update_cache()

            # Проверка бана для текущего пользователя
            if user_id in self.cache and current_time < self.cache[user_id]:
                logger.info(f"Сообщение от забаненного пользователя {user_id} проигнорировано")
                return
                
            # Проверка бана для оригинального отправителя (если сообщение переслано)
            original_user = None
            if event.forward_from:
                original_user = event.forward_from.id
            elif event.reply_to_message and event.reply_to_message.forward_from:
                original_user = event.reply_to_message.forward_from.id
            
            if original_user and original_user in self.cache and current_time < self.cache[original_user]:
                logger.info(f"Пересланное сообщение от забаненного пользователя {original_user} проигнорировано")
                return
                
            # Обновление времени активности состояния только для приватных чатов
            state: FSMContext = data.get('state')
            if state and await state.get_state() is not None and event.chat.type == "private":
                storage_key = StorageKey(
                    bot_id=event.bot.id,
                    chat_id=event.chat.id,
                    user_id=user_id
                )
                await state.update_data(last_activity=current_time)
                self.active_states.add(storage_key)
                logger.debug(f"Активность состояния обновлена для {user_id}")

            return await handler(event, data)
        except Exception as e:
            logger.error(f"Ошибка в middleware: {str(e)}")
            return await handler(event, data)
    
    async def check_states_timeout(self):
        """Проверяет и сбрасывает состояния по таймауту"""
        while True:
            await asyncio.sleep(10)
            current_time = time.time()
            timeout = parse_time(self.config.get("state_timeout", "30m"))
            
            for storage_key in list(self.active_states):
                try:
                    state = FSMContext(storage=self.storage, key=storage_key)
                    if not await state.get_state():
                        self.active_states.discard(storage_key)
                        continue
                        
                    data = await state.get_data()
                    last_activity = data.get("last_activity", 0)
                    
                    if current_time - last_activity > timeout:
                        # Получаем пользователя из данных состояния
                        user_data = await state.get_data()
                        user = user_data.get('user')  # Предполагаем, что пользователь сохранен в данных состояния
                        
                        if user and self.bot:
                            # Обновляем тему с emoji для unbanned
                            try:
                                topic_id = await get_or_create_topic(
                                    user=user,
                                    request_type="unbanned",  # Тип для unbanned
                                    bot=self.bot
                                )
                                logger.info(f"Тема обновлена с emoji unbanned для пользователя {user.id}")
                            except Exception as e:
                                logger.error(f"Ошибка при обновлении темы: {e}")
                        
                        await state.clear()
                        self.active_states.discard(storage_key)
                        logger.info(f"Состояние сброшено по таймауту для {storage_key.user_id}")
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки состояния: {e}")
                    self.active_states.discard(storage_key)


    async def close(self):
        """Остановка фоновых задач"""
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass
            logger.info("Фоновая задача остановлена")