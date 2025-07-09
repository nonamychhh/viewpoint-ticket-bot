import asyncio
import aiosqlite
import time
import datetime
import logging
from aiogram.dispatcher.router import Router
from aiogram.types import Message, User, CallbackQuery
from load_config import load_config, save_config
from aiogram import F, Bot
from aiogram.filters import Command, CommandStart, StateFilter
from buttons import *
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(f"logs/{__name__}.log", mode='a',encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

router = Router()
config = load_config()

FORUM_CHAT_ID = int(config["target_chat"])

def parse_time(time_str: str) -> int:
    """Преобразует строку времени в секунды"""
    if not isinstance(time_str, str):
        return 0

    if time_str.isdigit():
        return int(time_str)

    suffixes = {'m': 60, 'h': 3600, 'd': 86400}
    if time_str[:-1].isdigit() and time_str[-1].isalpha():
        suffix = time_str[-1].lower()
        if suffix in suffixes:
            return int(time_str[:-1]) * suffixes[suffix]
    return 0

async def init_chats_db():
    """Инициализирует базу данных для хранения чатов"""
    async with aiosqlite.connect('data/chat_links.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS chats
            (user_id INTEGER, 
             topic_id INTEGER,
             type TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS confirmations
            (user_id INTEGER PRIMARY KEY,
             last_sent REAL)''')
        await db.commit()
        logger.info("База данных чатов инициализирована")

async def get_or_create_topic(user: User, request_type: str, bot: Bot):
    """Создает или возвращает существующую тему для пользователя"""
    config = load_config()
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            logger.error("Целевой чат не настроен")
            return None

        user_id = user.id
        async with aiosqlite.connect('data/chat_links.db') as db:
            cursor = await db.execute(
                "SELECT topic_id, type FROM chats WHERE user_id = ?",
                (user_id,)
            )
            existing_topic = await cursor.fetchone()
            
            if existing_topic:
                topic_id, current_type = existing_topic
                if current_type != request_type:
                    username = f"@{user.username}" if user.username else "[Нет юзернейма]"
                    new_topic_name = f"{config["emojis"][request_type]["emoji"]} | {user.full_name} | {username}"
                    
                    await bot.edit_forum_topic(
                        chat_id=FORUM_CHAT_ID,
                        message_thread_id=topic_id,
                        name=new_topic_name
                    )
                    
                    await db.execute(
                        "UPDATE chats SET type = ? WHERE topic_id = ?",
                        (request_type, topic_id)
                    )
                    await db.commit()
                    logger.info(f"Тема обновлена для пользователя {user_id}")
                return topic_id
            
            username = f"@{user.username}" if user.username else "[Нет юзернейма]"
            topic_name = f"{config["emojis"][request_type]["emoji"]} | {user.full_name} | {username}"
            topic = await bot.create_forum_topic(
                chat_id=FORUM_CHAT_ID,
                name=topic_name
            )
            topic_id = topic.message_thread_id
            await db.execute(
                "INSERT INTO chats(user_id, topic_id, type) VALUES (?, ?, ?)",
                (user_id, topic_id, request_type)
            )
            await db.commit()
            logger.info(f"Создана новая тема для пользователя {user_id}")
        return topic_id
    except Exception as e:
        logger.error(f"Ошибка при создании темы: {str(e)}")
        return None

async def forward_to_user(topic_id: int, message: Message):
    """Пересылает сообщение пользователю в личные сообщения"""
    config = load_config()
    try:
        async with aiosqlite.connect('data/chat_links.db') as db:
            cursor = await db.execute(
                "SELECT user_id FROM chats WHERE topic_id = ?",
                (topic_id,)
            )
            result = await cursor.fetchone()
        if config["reply_mode"] == "free":
            pass

        if config["reply_mode"] == "necessary":
            # Обязательный режим — пересылаем ТОЛЬКО если:
            # 1. Это ответ (reply_to_message не None)
            # 2. И это ответ на сообщение бота (from_user.id == bot.id)
            if message.reply_to_message and message.reply_to_message.from_user.id == message.bot.id and message.reply_to_message.message_id != message.reply_to_message.message_thread_id: pass
            else: return
        if result is None:
            logger.warning(f"Тема {topic_id} не найдена в базе данных")
            return
        
        user_id = result[0]
        try:
            await message.send_copy(user_id)
            logger.info(f"Сообщение переслано пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка пересылки: {str(e)}")
            await message.reply(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {str(e)}")

class FormType(StatesGroup):
    """Состояния для обработки форм"""
    is_active = State()

class SettingsChange(StatesGroup):
    """Состояния для изменения настроек"""
    setting_changed = State()

request_filter = StateFilter(FormType.is_active)
settings_filter = StateFilter(SettingsChange.setting_changed)

translations = {
    "texts": {
        "greeting": "Приветственное сообщение",
        "application": "Текст заявки на вступление",
        "report": "Текст подачи жалобы", 
        "collaboration": "Текст заявки на сотрудничество",
        "staff": "Текст заявки на игровую должность",
        "event": "Текст заявки на проведение ивента",
        "reward": "Текст заявки на запрос награды",
        "other": "Текст для остального",
        "confirmation": "Текст подтверждения заявки"
    },
    "emojis": {
        "application": "Эмодзи заявки на вступление",
        "report": "Эмодзи подачи жалобы",
        "collaboration": "Эмодзи заявки на сотрудничество",
        "staff": "Эмодзи заявки на игровую должность",
        "event": "Эмодзи заявки на проведение ивента",
        "reward": "Эмодзи заявки на запрос награды",
        "other": "Эмодзи для остального"
    }
} 

@router.callback_query(F.data == "reset")
async def reset_state(call: CallbackQuery, state: FSMContext):
    """Сбрасывает текущее состояние"""
    await state.clear()
    await call.message.answer(config["texts"]["greeting"], reply_markup=start_keyboard)
    await call.answer()
    logger.info(f"Состояние сброшено для пользователя {call.from_user.id}")

@router.callback_query(F.data.startswith("request-"))
async def handle_start_buttons(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает кнопки главного меню"""
    action = callback.data.split("-")[1]
    texts = config.get("texts")
    response = texts.get(action)
    await state.set_state(None)
    await callback.answer()
    await callback.message.answer(response, reply_markup=cancel_markup)
    await state.set_state(FormType.is_active)
    await state.set_data({"type": action,"user": callback.from_user})
    logger.info(f"Пользователь {callback.from_user.id} начал заявку типа {action}")

@router.callback_query(F.data.startswith("settings"))
async def handle_settings_buttons(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает кнопки настроек"""
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            await callback.answer("❌ Целевой чат не настроен! Используйте /set_chat", show_alert=True)
            logger.error("Целевой чат не настроен при попытке доступа к настройкам")
            return

        user_id = callback.from_user.id
        try:
            chat_member = await callback.bot.get_chat_member(int(FORUM_CHAT_ID), user_id)
            if chat_member.status not in ['administrator', 'creator']:
                await callback.answer("❌ Только администраторы могут изменять настройки!", show_alert=True)
                logger.warning(f"Попытка доступа к настройкам без прав: {user_id}")
                return
        except Exception as e:
            await callback.answer(f"❌ Ошибка проверки прав: {str(e)}", show_alert=True)
            logger.error(f"Ошибка проверки прав: {str(e)}")
            return

        parts = callback.data.split("-")
        category = parts[1] if len(parts) > 1 else None
        subcategory = parts[2] if len(parts) > 2 else None
        await state.set_state(None)
        
        if category == "texts":
            if subcategory:
                current_text = config['texts'].get(subcategory, "❌ Текст не найден")
                await callback.message.edit_text(
                    f"{translations['texts'].get(subcategory)}\n"
                    f"Текущее значение: {current_text}\n\n"
                    "Отправьте новый текст:", reply_markup=keyboard_back
                )
                await state.set_state(SettingsChange.setting_changed)
                await state.set_data({"category": category, "subcategory": subcategory})
                logger.info(f"Начато изменение текста: {subcategory}")
            else:
                await callback.message.edit_text("📄 Настройки текстов:", reply_markup=texts_keyboard)
        elif category == "emojis":
            if subcategory:
                current_emoji = config['emojis'].get(subcategory, {}).get('emoji', '❌')
                await callback.message.edit_text(
                    f"{translations['emojis'].get(subcategory)}\n"
                    f"Текущий эмодзи: {current_emoji}\n\n"
                    "Отправьте новый эмодзи:", reply_markup=keyboard_back
                )
                await state.set_state(SettingsChange.setting_changed)
                await state.set_data({"category": category, "subcategory": subcategory})
                logger.info(f"Начато изменение эмодзи: {subcategory}")
            else:
                await callback.message.edit_text("Настройки эмодзи:", reply_markup=emojis_keyboard)
        elif category == "messages":
            await callback.message.edit_text(
                f"Текущий интервал: {config['cooldown']}\n"
                "Отправьте новый интервал (например: 30m, 2h):",
                reply_markup=keyboard_back
            )
            await state.set_state(SettingsChange.setting_changed)
            await state.set_data({"setting_type":"confirmation_cooldown"})
            logger.info("Начато изменение интервала подтверждений")
        elif category == "chat_mode":
            if subcategory:
                if subcategory == "chat":
                    config["chat_mode"] = "single"
                    save_config(config)
                    logger.info("Режим чата изменен на одиночный")
                elif subcategory == "topic":
                    config["chat_mode"] = "multiple"
                    save_config(config)
                    logger.info("Режим чата изменен на мульти-темы")
                await callback.message.answer("Настройка успешно изменена.")
                await callback.message.edit_text("Настройки бота:", reply_markup=settings_keyboard)
            else:
                await callback.message.edit_text("💬 Выберите режим чата:", reply_markup=chatmode_buttons)
        elif category == "reply_mode":
            if subcategory:
                if subcategory == "free":
                    config["reply_mode"] = "free"
                    save_config(config)
                    logger.info("Режим ответов изменен на свободный")
                elif subcategory == "necessary":
                    config["reply_mode"] = "necessary"
                    save_config(config)
                    logger.info("Режим ответов изменен на обязательный")
                await callback.message.answer("Настройка успешно изменена.")
                await callback.message.edit_text("Настройки бота:", reply_markup=settings_keyboard)
            else:
                await callback.message.edit_text("🛣️ Настройка способов ответа:", reply_markup=replyways_buttons)
        elif category == "interval":
            await callback.message.edit_text(
                f"Эта настройка отвечает за то, через сколько времени заявка сбросится.\n"
                f"Текущий интервал: {config["state_timeout"]}\n"
                "Отправьте новый интервал (например: 30m, 2h):",
                reply_markup=keyboard_back
            )
            await state.set_state(SettingsChange.setting_changed)
            await state.set_data({"setting_type":"request-reset-interval"})
            logger.info("Начато изменение интервала сброса заявок")
        else:
            await callback.message.edit_text("Настройки бота:", reply_markup=settings_keyboard)
        
        save_config(config)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка обработки настроек: {str(e)}")
        await callback.answer("❌ Произошла ошибка при обработке запроса")

@router.message(CommandStart(), F.chat.type == "private")
async def start(msg: Message):
    """Обработчик команды /start"""
    try:
        await msg.answer(config["texts"]["greeting"], reply_markup=start_keyboard)
        logger.info(f"Пользователь {msg.from_user.id} запустил бота")
    except Exception as e:
        logger.error(f"Ошибка в /start: {str(e)}")

@router.message(request_filter, F.chat.type == "private")
async def theme_choose(msg: Message, state: FSMContext):
    """
    Обрабатывает заявки пользователей в личных сообщениях.
    Промежуточное сообщение отправляется только если с момента последнего
    такого сообщения прошло больше времени, чем указано в cooldown.
    """
    try:
        if msg.from_user.id == msg.bot.id:
            return
            
        config = load_config()
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            await msg.answer("❌ Целевой чат не настроен! Используйте /set_chat")
            logger.error("Целевой чат не настроен при обработке заявки")
            return
        
        data = await state.get_data()
        request_type = data["type"]
        
        # Обработка в зависимости от режима чата
        if config.get("chat_mode") == "single":
            target_topic = config.get("target_topic", "general")
            try:
                if target_topic == "general":
                    await msg.forward(chat_id=FORUM_CHAT_ID)
                else:
                    await msg.forward(
                        chat_id=FORUM_CHAT_ID,
                        message_thread_id=int(target_topic)
                    )
                logger.info(f"Заявка переслана в одиночный чат (тема: {target_topic})")
            except Exception as e:
                logger.error(f"Ошибка пересылки в одиночный чат: {str(e)}")
                await msg.answer("❌ Ошибка при отправке заявки")
                return
        else:
            try:
                topic_id = await get_or_create_topic(msg.from_user, request_type, msg.bot)
                if topic_id is None:
                    await msg.answer("❌ Ошибка: не удалось создать тему")
                    return
                    
                await msg.send_copy(
                    chat_id=FORUM_CHAT_ID,
                    message_thread_id=topic_id
                )
                logger.info(f"Заявка переслана в тему {topic_id}")
            except Exception as e:
                logger.error(f"Ошибка пересылки в индивидуальную тему: {str(e)}")
                await msg.answer("❌ Ошибка при отправке заявки")
                return
        
        # Проверка cooldown для промежуточного сообщения
        current_time = time.time()
        async with aiosqlite.connect('data/chat_links.db') as db:
            cursor = await db.execute(
                "SELECT last_sent FROM confirmations WHERE user_id = ?",
                (msg.from_user.id,)
            )
            last_sent = await cursor.fetchone()

            cooldown = parse_time(config["cooldown"])
            
            # Отправляем сообщение только если cooldown истек или его не было
            if not last_sent or (current_time - last_sent[0]) > cooldown:
                try:
                    await msg.answer(config["texts"]["confirmation"])
                    await db.execute(
                        '''INSERT OR REPLACE INTO confirmations 
                        (user_id, last_sent) VALUES (?, ?)''',
                        (msg.from_user.id, current_time)
                    )
                    await db.commit()
                    logger.info(f"Подтверждение отправлено пользователю {msg.from_user.id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки подтверждения: {str(e)}")
        
        # Не очищаем состояние, чтобы пользователь мог отправлять несколько сообщений
        logger.info(f"Заявка пользователя {msg.from_user.id} обработана")
        
    except Exception as e:
        logger.error(f"Ошибка обработки заявки: {str(e)}")
        await msg.answer("❌ Произошла ошибка при обработке вашей заявки")

@router.message(Command("ban"), F.chat.id == FORUM_CHAT_ID)
async def ban_command(message: Message, bot: Bot):
    """Бан пользователя"""
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            await message.reply("❌ Целевой чат не настроен! Используйте /set_chat")
            return

        try:
            chat_member = await bot.get_chat_member(int(FORUM_CHAT_ID), message.from_user.id)
            if chat_member.status not in ['administrator', 'creator']:
                await message.reply("❌ Только администраторы могут использовать эту команду")
                return
        except Exception as e:
            await message.reply(f"❌ Ошибка проверки прав: {str(e)}")
            return

        if config.get("chat_mode") == "single":
            if not message.reply_to_message or not message.reply_to_message.forward_from:
                await message.reply("⚠ Ответьте на пересланное сообщение пользователя!")
                return
            user_id = message.reply_to_message.forward_from.id
        else:
            if not message.message_thread_id:
                await message.reply("⚠ Эту команду можно использовать только в форумной теме!")
                return
            
            async with aiosqlite.connect('data/chat_links.db') as db:
                cursor = await db.execute(
                    "SELECT user_id FROM chats WHERE topic_id = ?",
                    (message.message_thread_id,)
                )
                result = await cursor.fetchone()
                if not result:
                    await message.reply("❌ Тема не найдена в базе данных")
                    return
                user_id = result[0]

        args = message.text.split()
        duration = None
        
        if len(args) >= 2:
            time_arg = args[1]
            duration = parse_time(time_arg)
            if duration <= 0:
                await message.reply("⛔ Некорректный формат времени. Используйте:\nm - минуты\nh - часы\nd - дни")
                return

        if duration:
            ban_end = datetime.datetime.now() + datetime.timedelta(seconds=duration)
            timestamp = ban_end.timestamp()
            time_info = f"⏳ Срок: {time_arg}\n"
            ban_end_str = ban_end.strftime('%Y-%m-%d %H:%M:%S')
        else:
            ban_end = datetime.datetime.now() + datetime.timedelta(days=365*100)
            timestamp = ban_end.timestamp()
            time_info = ""
            ban_end_str = "♾️"
        
        reason = " ".join(args[2:]) if len(args) > 2 else ""
        
        banning_user = await bot.get_chat_member(int(FORUM_CHAT_ID), user_id)
        if banning_user.status in ["administrator","creator"]:
            await message.reply("Вы не можете забанить администратора бота")
            return

        async with aiosqlite.connect('data/bans.db') as db:
            await db.execute(
                '''INSERT OR REPLACE INTO ignored_users (user_id, ban_end) 
                VALUES (?, ?)''',
                (user_id, timestamp)
            )
            await db.commit()
            logger.info(f"Пользователь {user_id} забанен")

        reply_text = (
            f"🚫 Пользователь [ID:{user_id}] будет забанен до "
            f"{ban_end_str}\n"
            f"{time_info}"
            f"Причина: {reason}" if reason else ""
        )
        await message.reply(reply_text)

        try:
            notification_text = (f"⛔ Вы были временно забанены до {ban_end_str}\nПричина: {reason}" 
                if duration else f"⛔ Вы были забанены навсегда\nПричина: {reason}")
            await bot.send_message(user_id, text=notification_text)
        except Exception as e:
            logger.error(f"Ошибка уведомления о бане: {str(e)}")
            await message.reply(f"⚠ Не удалось уведомить пользователя: {str(e)}")
        
        user_info = await bot.get_chat(user_id)
        user = User(
            id=user_id, 
            is_bot=False, 
            first_name=user_info.first_name, 
            last_name=user_info.last_name, 
            username=user_info.username
        )
        await get_or_create_topic(user, "banned", bot)
    except Exception as e:
        logger.error(f"Ошибка бана пользователя: {str(e)}")
        await message.reply(f"❌ Произошла ошибка: {str(e)}")

@router.message(Command("unban"), F.chat.id == FORUM_CHAT_ID)
async def unban_command(message: Message, bot: Bot):
    """Разбан пользователя"""
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            await message.reply("❌ Целевой чат не настроен! Используйте /set_chat")
            return

        try:
            chat_member = await bot.get_chat_member(int(FORUM_CHAT_ID), message.from_user.id)
            if chat_member.status not in ['administrator', 'creator']:
                await message.reply("❌ Только администраторы могут использовать эту команду")
                return
        except Exception as e:
            await message.reply(f"❌ Ошибка проверки прав: {str(e)}")
            return

        if not message.message_thread_id:
            await message.reply("⚠ Эту команду можно использовать только в форумной теме!")
            return

        topic_id = message.message_thread_id

        async with aiosqlite.connect('data/chat_links.db') as db:
            cursor = await db.execute(
                "SELECT user_id FROM chats WHERE topic_id = ?",
                (topic_id,)
            )
            result = await cursor.fetchone()

        if not result:
            await message.reply("❌ Тема не найдена в базе данных")
            return

        user_id = result[0]

        async with aiosqlite.connect('data/bans.db') as db:
            cursor = await db.execute(
                "DELETE FROM ignored_users WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

        if cursor.rowcount > 0:
            await message.reply(f"✅ Пользователь [ID:{user_id}] успешно разбанен")
            logger.info(f"Пользователь {user_id} разбанен")
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="✅ Ваша блокировка была снята."  
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления о разбане: {str(e)}")
                await message.reply(f"⚠ Не удалось уведомить пользователя: {str(e)}")
        
            user_info = await bot.get_chat(user_id)
            user = User(
                id=user_id, 
                is_bot=False, 
                first_name=user_info.first_name, 
                last_name=user_info.last_name, 
                username=user_info.username
            )
            await get_or_create_topic(user, "unbanned", bot)
        else:
            await message.reply("ℹ Пользователь не был забанен")
    except Exception as e:
        logger.error(f"Ошибка разбана пользователя: {str(e)}")
        await message.reply(f"❌ Произошла ошибка: {str(e)}")

@router.message(settings_filter)
async def change_setting(msg: Message, state: FSMContext):
    """Изменяет настройки бота"""
    try:
        data = await state.get_data()
        
        if data.get("setting_type") == "confirmation_cooldown":
            new_cooldown = msg.text
            cooldown_value = parse_time(new_cooldown)
            if cooldown_value <= 0:
                await msg.answer("❌ Неверный формат времени!")
                return
                
            config["cooldown"] = new_cooldown
            save_config(config)
            await msg.answer("✅ Интервал подтверждений обновлен!")
            await state.clear()
            logger.info(f"Интервал подтверждений изменен на {new_cooldown}")
            return
            
        elif data.get("setting_type") == "request-reset-interval":
            new_interval = msg.text
            interval_value = parse_time(new_interval)
            if interval_value <= 0:
                await msg.answer("❌ Неверный формат времени!")
                return
                
            config["state_timeout"] = new_interval
            save_config(config)
            await msg.answer("✅ Интервал сброса заявок обновлен!")
            await state.clear()
            logger.info(f"Интервал сброса заявок изменен на {new_interval}")
            return

        category = data["category"]
        subcategory = data["subcategory"]
        
        if category == "emojis":
            config[category][subcategory]["emoji"] = msg.text[0]
            logger.info(f"Эмодзи {subcategory} изменен на {msg.text[0]}")
        else:
            config[category][subcategory] = msg.text
            logger.info(f"Текст {subcategory} изменен")
        
        await msg.answer("Шаблон успешно изменен.")
        save_config(config)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка изменения настроек: {str(e)}")
        await msg.answer("❌ Произошла ошибка при изменении настроек")

@router.message(Command("set_chat"))
async def send_chat_id(msg: Message):
    """Устанавливает целевой чат"""
    config = load_config()
    config["target_chat"] = str(msg.chat.id)
    save_config(config)
    await msg.answer(f"✅ Целевой чат установлен! ID: {msg.chat.id}")
    logger.info(f"Установлен целевой чат: {msg.chat.id}")

@router.message(Command("set_topic"), F.chat.id == FORUM_CHAT_ID)
async def set_topic(msg: Message):
    """Устанавливает тему для одиночного режима"""
    config = load_config()
    target_topic = msg.message_thread_id if msg.message_thread_id else "general"
    config["target_topic"] = target_topic
    save_config(config)
    await msg.answer(f"✅ Тема для одиночного режима установлена! ID: {target_topic}")
    logger.info(f"Установлена тема для одиночного режима: {target_topic}")

@router.message(Command("settings"), F.chat.id == FORUM_CHAT_ID)
async def settings(msg: Message, state: FSMContext):
    """Открывает меню настроек"""
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID:
            await msg.answer("❌ Целевой чат не настроен! Используйте /set_chat")
            return

        user = await msg.bot.get_chat_member(int(FORUM_CHAT_ID), msg.from_user.id)
        if user.status in ["administrator","creator"]:
            await msg.answer("Настройки бота:", reply_markup=settings_keyboard)
            logger.info(f"Пользователь {msg.from_user.id} открыл настройки")
    except Exception as e:
        logger.error(f"Ошибка открытия настроек: {str(e)}")

@router.message(Command("help"), F.chat.id == FORUM_CHAT_ID)
async def help_command(message: Message):
    """Показывает справку по командам"""
    help_text = (
        "Команды бота:\n"
        "/start - Начать взаимодействие с ботом(в ЛС)\n"
        "/settings - Настройки бота(только для создателя чата)\n"
        "/set_chat - Установить целевой чат для заявок\n"
        "/set_topic - Установить тему для одиночного режима\n"
        "/ban (время(опционально)) (причина(опционально)) - Забанить пользователя\n"
        "/unban - Разбанить пользователя\n"
        "/help - Показать это сообщение\n"
    )
    await message.answer(help_text)
    logger.info("Отправлена справка по командам")

@router.message(F.chat.id == FORUM_CHAT_ID)
async def handle_forum_message(message: Message):
    """Обрабатывает сообщения в форумном чате"""
    config = load_config()
    try:
        FORUM_CHAT_ID = config.get("target_chat")
        if not FORUM_CHAT_ID or message.chat.id != int(FORUM_CHAT_ID):
            return
        
        if not message.message_thread_id or message.from_user.id == message.bot.id:
            return

        
        await forward_to_user(message.message_thread_id, message)
    except Exception as e:
                logger.error(f"Ошибка обработки форумного сообщения: {str(e)}")

@router.message(F.chat.type == "private")
async def handle_private_message(message: Message):
    """Обрабатывает личные сообщения"""
    try:
        await message.answer(config["texts"]["greeting"], reply_markup=start_keyboard)
    except Exception as e:
        logger.error(f"Ошибка обработки личного сообщения: {str(e)}")