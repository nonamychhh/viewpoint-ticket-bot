import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import handlers
from load_config import load_config
from middlewares import AsyncIgnoreMiddleware
import aiosqlite
from aiogram.client.default import DefaultBotProperties

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(f"logs/{__name__}.log", mode='a',encoding='utf-8')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

session = AiohttpSession()

async def main():
    """Основная функция инициализации бота"""
    try:
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
            logger.info("База данных банов инициализирована")

        bot = Bot(
            token=load_config()["API_TOKEN"], 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML), 
            session=session
        )
        dp = Dispatcher(storage=MemoryStorage())
        
        # Подключение middleware
        dp.message.middleware(AsyncIgnoreMiddleware(storage=dp.storage))
        dp.include_router(handlers.router)
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот запущен")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {str(e)}")

if __name__ == "__main__":
    # Настройка корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/bot.log",encoding='utf-8'),
            logging.StreamHandler()
        ],
        
    )
    
    try:
        asyncio.run(main())
    finally:
        session.close()
        logger.info("Сессия бота закрыта")