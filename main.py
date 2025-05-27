import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import handlers
from load_config import load_config, save_config
from middlewares import AsyncIgnoreMiddleware
import aiosqlite
from aiogram.client.default import DefaultBotProperties
session = AiohttpSession()

async def main():
    # Инициализация баз данных
    await handlers.init_chats_db()
    
    # Инициализация базы банов
    async with aiosqlite.connect('data/bans.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS ignored_users (
            user_id INTEGER PRIMARY KEY,
            ban_end REAL NOT NULL
        )''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_ban_end ON ignored_users(ban_end)')
        await db.commit()

    bot = Bot(token=load_config()["API_TOKEN"], default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключение middleware
    dp.message.middleware(AsyncIgnoreMiddleware())
    dp.include_router(handlers.router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
    session.close()