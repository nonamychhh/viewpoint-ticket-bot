import time
import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import Message

DATABASE = 'data/bans.db'
CACHE_TTL = 60  # seconds

class AsyncIgnoreMiddleware(BaseMiddleware):
    def __init__(self):
        self.cache = {}
        self.last_cache_update = 0
        self.cache_ttl = CACHE_TTL
        self.db_path = DATABASE

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

        return await handler(event, data)