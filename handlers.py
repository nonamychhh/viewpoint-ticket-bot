import asyncio
import aiosqlite
import time
import datetime
from aiogram.dispatcher.router import Router
from aiogram.types import Message, User, ReplyKeyboardRemove, CallbackQuery
from load_config import load_config, save_config
from aiogram import F
from aiogram.filters import Command, CommandStart, StateFilter
from buttons import *
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot

router = Router()
config = load_config()
FORUM_CHAT_ID = int(config.get("target_chat"))

def parse_time(time_str: str) -> int:
    suffixes = {'m': 60, 'h': 3600, 'd': 86400}
    suffix = time_str[-1].lower()
    if suffix not in suffixes:
        return 0
    return int(time_str[:-1]) * suffixes[suffix]

async def init_chats_db():
    async with aiosqlite.connect('data/chat_links.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS chats
            (user_id INTEGER, 
             topic_id INTEGER,
             type TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS confirmations
            (user_id INTEGER PRIMARY KEY,
             last_sent REAL)''')
        await db.commit()

async def get_or_create_topic(user: User, request_type: str, bot: Bot):
    user_id = user.id
    async with aiosqlite.connect('data/chat_links.db') as db:
        cursor = await db.execute(
            "SELECT topic_id FROM chats WHERE user_id = ? AND type = ?",
            (user_id, request_type)
        )
        topic_id = await cursor.fetchone()
        
        if topic_id is None:
            username = f"@{user.username}" if user.username else "[Нет юзернейма]"
            topic_name = f"{request_type} {user.full_name} {username}"
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
    
    return topic_id[0] if isinstance(topic_id, tuple) else topic_id

async def forward_to_user(topic_id: int, message: Message):
    async with aiosqlite.connect('data/chat_links.db') as db:
        cursor = await db.execute(
            "SELECT user_id FROM chats WHERE topic_id = ?",
            (topic_id,)
        )
        result = await cursor.fetchone()
        
    if result is None:
        return
    
    user_id = result[0]
    try:
        await message.bot.send_message(user_id, message.text)
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")

class FormType(StatesGroup):
    is_active = State()

class SettingsChange(StatesGroup):
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

@router.callback_query(F.data.startswith("request-"))
async def handle_start_buttons(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("-")[1]
    texts = config.get("texts")
    response = texts.get(action)
    
    await callback.answer()
    await callback.message.answer(response, reply_markup=cancel_markup)
    await state.set_state(FormType.is_active)
    await state.set_data({"type": action})

@router.callback_query(F.data.startswith("settings"))
async def handle_settings_buttons(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_creator = await callback.bot.get_chat_member(FORUM_CHAT_ID,user_id)
    if is_creator.status != "creator":
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
        else:
            await callback.message.edit_text("😀 Настройки эмодзи:", reply_markup=emojis_keyboard)
    elif category == "messages":
        await callback.message.edit_text(
            f"Текущий интервал: {config['cooldown']}\n"
            "Отправьте новый интервал (например: 30m, 2h):",
            reply_markup=keyboard_back
        )
        await state.set_state(SettingsChange.setting_changed)
        await state.set_data({"setting_type":"confirmation_cooldown"})
    elif category == "chat_mode":
        if subcategory:
            if subcategory == "chat":
                config["chat_mode"] = "single"
                save_config(config)
            elif subcategory == "topic":
                config["chat_mode"] = "multiple"
                save_config(config)
        else:
            await callback.message.edit_text("💬 Выберите режим чата:", reply_markup=chatmode_buttons)
    elif category == "reply_ways":
        await callback.message.edit_text("🛣️ Настройка способов ответа:", reply_markup=replyways_buttons)
    else:
        await callback.message.edit_text("Настройки бота:", reply_markup=settings_keyboard)
    
    save_config(config)
    await callback.answer()

@router.message(CommandStart(), F.chat.type == "private")
async def start(msg: Message):
    await msg.answer(config["texts"]["greeting"], reply_markup=start_keyboard)

@router.message(request_filter, F.chat.type == "private")
async def theme_choose(msg: Message, state: FSMContext):
    if msg.from_user.id == msg.bot.id:
        return
    
    if FORUM_CHAT_ID is None:
        await msg.answer("❌ Целевой чат не настроен! Используйте /set_chat")
        return
    
    data = await state.get_data()
    request_type = data["type"]
    
    # Режим одиночного чата
    if config.get("chat_mode") == "single":
        if not config.get("target_topic"):
            await msg.answer("❌ Тема для заявок не настроена!")
            return
            
        await msg.forward(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=config["target_topic"]
        )
    else:
        topic_id = await get_or_create_topic(msg.from_user, config["emojis"][request_type]["emoji"], msg.bot)
        await msg.send_copy(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=topic_id
        )
    
    current_time = time.time()
    async with aiosqlite.connect('data/chat_links.db') as db:
        cursor = await db.execute(
            "SELECT last_sent FROM confirmations WHERE user_id = ?",
            (msg.from_user.id,)
        )
        last_sent = await cursor.fetchone()

        cooldown = parse_time(config["cooldown"])
        
        if not last_sent or (current_time - last_sent[0]) > cooldown:
            await msg.answer(config["texts"]["confirmation"])
            await db.execute(
                '''INSERT OR REPLACE INTO confirmations 
                (user_id, last_sent) VALUES (?, ?)''',
                (msg.from_user.id, current_time)
            )
            await db.commit()


@router.message(Command("ban"))
async def ban_command(message: Message, bot: Bot):
    try:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
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
    time_arg = None
    duration = None
    
    if len(args) >= 2:
        time_arg = args[1]
        duration = parse_time(time_arg)
        if duration and duration <= 0:
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

    banning_user = await bot.get_chat_member(FORUM_CHAT_ID, user_id)
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

    reply_text = (
        f"🚫 Пользователь [ID:{user_id}] будет игнорироваться до "
        f"{ban_end_str}\n"
        f"{time_info}"
    )
    await message.reply(reply_text)

    try:
        notification_text = (f"⛔ Вы были временно забанены до {ban_end_str}" 
            if duration else "⛔ Вы были забанены навсегда ♾️")
        await bot.send_message(user_id, text=notification_text)
    except Exception as e:
        await message.reply(f"⚠ Не удалось уведомить пользователя: {str(e)}")

@router.message(Command("unban"))
async def unban_command(message: Message, bot: Bot):
    try:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
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
        await message.reply(f"✅ Пользователь [ID:{user_id}] успешно разбанен\n")
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Ваш бан был снят! Теперь вы снова можете отправлять сообщения"
            )
        except Exception as e:
            await message.reply(f"⚠ Не удалось уведомить пользователя: {str(e)}")
    else:
        await message.reply("ℹ Пользователь не был забанен")

@router.message(settings_filter)
async def change_setting(msg: Message, state: FSMContext):
    data = await state.get_data()
    
    if data.get("setting_type") == "confirmation_cooldown":
        new_cooldown = msg.text
        if parse_time(new_cooldown) <= 0:
            await msg.answer("❌ Неверный формат времени!")
            return
            
        config["cooldown"] = new_cooldown
        save_config(config)
        await msg.answer("✅ Интервал подтверждений обновлен!")
        return
    
    category = data["category"]
    subcategory = data["subcategory"]
    
    if category == "emojis":
        config[category][subcategory]["emoji"] = msg.text[0]
    else:
        config[category][subcategory] = msg.text
    
    await msg.answer("Шаблон успешно изменен.")
    save_config(config)
    await state.set_state(None)
@router.message(Command("set_chat"))
async def send_chat_id(msg: Message):
    global FORUM_CHAT_ID
    config = load_config()
    config["target_chat"] = str(msg.chat.id)
    save_config(config)
    FORUM_CHAT_ID = msg.chat.id
    await msg.answer(f"Целевой чат установлен! ID: {msg.chat.id}")

@router.message(Command("set_topic"))
async def set_topic(msg: Message):
    global FORUM_CHAT_ID
    config["target_topic"] = msg.message_thread_id
    save_config(config)
    await msg.answer(f"Тема для одиночного режима установлена! ID: {msg.message_thread_id}")

@router.message(Command("settings"))
async def settings(msg: Message,state: FSMContext):
    user = await msg.bot.get_chat_member(FORUM_CHAT_ID,msg.from_user.id)
    if user.status == "creator":
        await msg.answer("Настройки бота:", reply_markup=settings_keyboard)

@router.message()
async def handle_forum_message(message: Message):
    if not FORUM_CHAT_ID or message.chat.id != FORUM_CHAT_ID:
        return
    
    if not message.message_thread_id or message.from_user.id == message.bot.id:
        return
    
    await forward_to_user(message.message_thread_id, message)