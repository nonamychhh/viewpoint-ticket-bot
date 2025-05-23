import asyncio
from aiogram import Bot,Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import handlers
from load_config import load_config,save_config


session = AiohttpSession()

async def main():
    bot = Bot(token=load_config()["API_TOKEN"], parse_mode=ParseMode.HTML,session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers.router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())

save_config(handlers.config)
session.close()