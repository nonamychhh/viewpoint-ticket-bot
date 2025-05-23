import asyncio
from aiogram.dispatcher.router import Router
from aiogram.types import Message, User,ReplyKeyboardRemove,CallbackQuery
from load_config import load_config, save_config
from aiogram import F
from aiogram.filters import Command,CommandStart,StateFilter
import sqlite3
from buttons import *
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
conn = sqlite3.connect('data/chat_links.db')
cur = conn.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS chats
             (user_id INTEGER, 
              topic_id INTEGER,
              type TEXT)''')
conn.commit()  # Не забываем коммитить изменения

router = Router()
# Загружаем конфиг при старте
config = load_config()
FORUM_CHAT_ID = int(config.get("target_chat"))

async def get_or_create_topic(user: User, request_type: str, bot: Bot):
    """Создает или возвращает тему пользователя"""
    user_id = user.id
    # Используем параметризованные запросы
    topic_id = cur.execute("SELECT topic_id FROM chats WHERE user_id = ? AND type = ?", (user_id, request_type)).fetchone()
    if topic_id is None:
        topic_name = f"[{request_type}] {user.full_name} {"@"+user.username if user.username is not None else "[Нет юзернейма]"}"
        topic = await bot.create_forum_topic(
            chat_id=FORUM_CHAT_ID,
            name=topic_name
        )
        topic_id = topic.message_thread_id
        cur.execute("INSERT INTO chats(user_id, topic_id, type) VALUES (?, ?, ?)", 
                   (user_id, topic_id, request_type))
        conn.commit()  # Сохраняем изменения в БД
    
    return topic_id[0] if type(topic_id) == tuple else topic_id

async def forward_to_user(topic_id: int, message: Message):
    """Пересылает сообщение из темы пользователю"""
    cur.execute("SELECT user_id FROM chats WHERE topic_id = ?", (topic_id,))
    result = cur.fetchone()
    
    if result is None:
        return
    
    user_id = result[0]
    try:
        await message.bot.send_message(user_id,message.text)
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
async def handle_start_buttons(callback: CallbackQuery,state: FSMContext):
    action = callback.data.split("-")[1]
    
    texts = config.get("texts")
    response = texts.get(action)
    
    await callback.answer()
    await callback.message.answer(response,reply_markup=cancel_markup)
    await state.set_state(FormType.is_active)
    await state.set_data({"type": action})

@router.callback_query(F.data.startswith("settings"))
async def handle_settings_buttons(callback: CallbackQuery,state: FSMContext):
    parts = callback.data.split("-")
    category = parts[1] if len(parts) > 1 else None
    subcategory = parts[2] if len(parts) > 2 else None
    await state.set_state(None)
    if category == "texts":
        if subcategory:
            current_text = config['texts'].get(subcategory, "❌ Текст не найден")
            await callback.message.edit_text(
                f"{translations["texts"].get(subcategory)}\n"
                f"Текущее значение: {current_text}\n\n"
                "Отправьте новый текст:",reply_markup=keyboard_back
            )
            
            await state.set_state(SettingsChange.setting_changed)
            await state.set_data({"category": category,"subcategory": subcategory})
        else:
            await callback.message.edit_text("📄 Настройки текстов:", reply_markup=texts_keyboard)
            
    elif category == "emojis":
        if subcategory:
            current_emoji = config['emojis'].get(subcategory, {}).get('emoji', '❌')
            await callback.message.edit_text(
                f"🎭 Выбор эмодзи для: {subcategory}\n"
                f"Текущий эмодзи: {current_emoji}\n\n"
                "Отправьте новый эмодзи:",reply_markup=keyboard_back
            )
            await state.set_state(SettingsChange.setting_changed)
            await state.set_data({"category": category,"subcategory": subcategory})
        else:
            await callback.message.edit_text("😀 Настройки эмодзи:", reply_markup=emojis_keyboard)
            
    elif category == "messages":
        await callback.message.edit_text("🔄 Настройка промежуточных сообщений...",reply_markup=keyboard_back)
        
    elif category == "chat_mode":
        await callback.message.edit_text("💬 Выберите режим чата:", reply_markup=chatmode_buttons)
        
    elif category == "reply_ways":
        await callback.message.edit_text("🛣️ Настройка способов ответа:", reply_markup=replyways_buttons)
    else:
        await callback.message.edit_text("Настройки бота:",reply_markup=settings_keyboard)
    await callback.answer()
    save_config(config)


@router.message(CommandStart(),F.chat.type == "private")
async def start(msg: Message):
    await msg.answer(config["texts"]["greeting"],reply_markup=start_keyboard)

@router.message(request_filter,F.chat.type == "private")
async def theme_choose(msg: Message,state: FSMContext):
    if msg.from_user.id == msg.bot.id:
        return
    
    if FORUM_CHAT_ID is None:
        await msg.answer("❌ Целевой чат не настроен! Используйте /set_chat")
        return
    data = await state.get_data()
    request_type = data["type"]

    topic_id = await get_or_create_topic(msg.from_user,config["emojis"][request_type]["emoji"],msg.bot)
    
    await msg.send_copy(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=topic_id )   
     
@router.message(settings_filter)
async def change_setting(msg: Message, state: FSMContext):
    data = await state.get_data()
    category = data["category"]
    subcategory = data["subcategory"]
    if category == "emojis":
        config[category][subcategory]["emoji"] = msg.text[0]
    else:
        config[category][subcategory] = msg.text
    await msg.answer("Шаблон успешно изменен.")
    print(msg.text[0])
    print(config)
    save_config(config)
@router.message(Command("set_chat"))
async def send_chat_id(msg: Message):
    global FORUM_CHAT_ID
    
    if FORUM_CHAT_ID and msg.chat.id == FORUM_CHAT_ID:
        await msg.answer("Этот чат уже установлен как целевой.")
        return
    
    config = load_config()
    config["target_chat"] = str(msg.chat.id)
    save_config(config)
    
    FORUM_CHAT_ID = msg.chat.id
    await msg.answer(f"Целевой чат установлен! ID: {msg.chat.id}")
    
@router.message(Command("settings"))
async def settings(msg: Message):
    await msg.answer("Настройки бота:",reply_markup=settings_keyboard)        

@router.message()
async def handle_forum_message(message: Message):
    if not FORUM_CHAT_ID or message.chat.id != FORUM_CHAT_ID:
        return
    
    if not message.message_thread_id or message.from_user.id == message.bot.id:
        return
    
    await forward_to_user(message.message_thread_id, message)