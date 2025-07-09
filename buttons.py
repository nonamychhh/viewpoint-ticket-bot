from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Кнопка "Назад" для возврата в меню настроек
button_back = InlineKeyboardButton(
    text="Назад",
    callback_data="settings"
)

# Кнопка "Отмена" для сброса состояния
cancel_button = InlineKeyboardButton(
    text="Отмена",
    callback_data="reset"
)

# Основные кнопки главного меню
button_request = InlineKeyboardButton(
    text="Подать заявку на вступление",
    callback_data="request-application"
)
button_affiliation = InlineKeyboardButton(
    text="Предложить сотрудничество",
    callback_data="request-collaboration"
)
button_report = InlineKeyboardButton(
    text="Подать жалобу",
    callback_data="request-report"
)
button_staff = InlineKeyboardButton(
    text="Подать заявку на игровую должность",
    callback_data="request-staff"
)
button_event = InlineKeyboardButton(
    text="Подать заявку на проведение ивента",
    callback_data="request-event"
)
button_reward = InlineKeyboardButton(
    text="Запросить награду",
    callback_data="request-reward"
)
button_other = InlineKeyboardButton(
    text="Другое",
    callback_data="request-other"
)

# Кнопки настроек текстов
texts_button = InlineKeyboardButton(
    text="Текста",
    callback_data="settings-texts"
)
texts_greeting_button = InlineKeyboardButton(
    text="Приветственное сообщение",
    callback_data="settings-texts-greeting"
)
texts_application_button = InlineKeyboardButton(
    text="Текст заявки на вступление",
    callback_data="settings-texts-application"
)
texts_report_button = InlineKeyboardButton(
    text="Текст подачи жалобы",
    callback_data="settings-texts-report"
)
texts_collaboration_button = InlineKeyboardButton(
    text="Текст заявки на сотрудничество",
    callback_data="settings-texts-collaboration"
)
texts_staff_button = InlineKeyboardButton(
    text="Текст заявки на игровую должность",
    callback_data="settings-texts-staff"
)
texts_event_button = InlineKeyboardButton(
    text="Текст заявки на проведение ивента",
    callback_data="settings-texts-event"
)
texts_reward_button = InlineKeyboardButton(
    text="Текст заявки на запрос награды",
    callback_data="settings-texts-reward"
)
texts_other_button = InlineKeyboardButton(
    text="Текст для остального",
    callback_data="settings-texts-other"
)
texts_confirmation_button = InlineKeyboardButton(
    text="Текст подтверждения заявки",
    callback_data="settings-texts-confirmation"
)

# Кнопки настроек чата
messages_button = InlineKeyboardButton(
    text="Настройка промежуточных сообщений",
    callback_data="settings-messages"
)
chatmode_button = InlineKeyboardButton(
    text="Режим чата",
    callback_data="settings-chat_mode"
)
chatmode_chat_button = InlineKeyboardButton(
    text="Режим одиночного чата",
    callback_data="settings-chat_mode-chat"
)
chatmode_topic_button = InlineKeyboardButton(
    text="Режим тем",
    callback_data="settings-chat_mode-topic"
)

# Кнопки интервалов и ответов
interval_button = InlineKeyboardButton(
    text="Интервал между сообщениями",
    callback_data="settings-interval"
)
replymode_button = InlineKeyboardButton(
    text="Способы ответа(режим тем)",
    callback_data="settings-reply_mode"
)
replyways_free_button = InlineKeyboardButton(
    text="Свободный ответ",
    callback_data="settings-reply_mode-free"
)
replyways_necessary_button = InlineKeyboardButton(
    text="Обязательный ответ",
    callback_data="settings-reply_mode-necessary"
)

# Кнопки настроек эмодзи
emojis_button = InlineKeyboardButton(
    text="Эмодзи в заявках(режим тем)",
    callback_data="settings-emojis"
)
emojis_application_button = InlineKeyboardButton(
    text="Эмодзи заявки на вступление",
    callback_data="settings-emojis-application"
)
emojis_report_button = InlineKeyboardButton(
    text="Эмодзи подачи жалобы",
    callback_data="settings-emojis-report"
)
emojis_collaboration_button = InlineKeyboardButton(
    text="Эмодзи заявки на сотрудничество",
    callback_data="settings-emojis-collaboration"
)
emojis_staff_button = InlineKeyboardButton(
    text="Эмодзи заявки на игровую должность",
    callback_data="settings-emojis-staff"
)
emojis_event_button = InlineKeyboardButton(
    text="Эмодзи заявки на проведение ивента",
    callback_data="settings-emojis-event"
)
emojis_reward_button = InlineKeyboardButton(
    text="Эмодзи заявки на запрос награды",
    callback_data="settings-emojis-reward"
)
emojis_other_button = InlineKeyboardButton(
    text="Эмодзи для остального",
    callback_data="settings-emojis-other"
)
emojis_banned_button = InlineKeyboardButton(
    text="Эмодзи забаненного пользователя",
    callback_data="settings-emojis-banned"
)
emojis_unbanned_button = InlineKeyboardButton(
    text="Эмодзи разбаненного пользователя",
    callback_data="settings-emojis-unbanned"
)

# Клавиатуры
start_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [button_request],
        [button_event],
        [button_staff],
        [button_reward, button_affiliation],
        [button_report, button_other]
    ]
)

settings_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [texts_button],
        [messages_button],
        [chatmode_button],
        [interval_button],
        [replymode_button, emojis_button]
    ]
)

replyways_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [replyways_free_button],
        [replyways_necessary_button],
        [button_back]
    ]
)

chatmode_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [chatmode_chat_button],
        [chatmode_topic_button],
        [button_back]
    ]
)

texts_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [texts_greeting_button],
        [texts_application_button],
        [texts_report_button],
        [texts_collaboration_button],
        [texts_staff_button],
        [texts_event_button],
        [texts_reward_button],
        [texts_other_button],
        [texts_confirmation_button],
        [button_back]
    ]
)

emojis_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [emojis_application_button],
        [emojis_report_button],
        [emojis_collaboration_button],
        [emojis_staff_button],
        [emojis_event_button],
        [emojis_reward_button],
        [emojis_other_button],
        [emojis_banned_button],
        [emojis_unbanned_button],
        [button_back]
    ]
)

keyboard_back = InlineKeyboardMarkup(
    inline_keyboard=[[button_back]]
)

cancel_markup = InlineKeyboardMarkup(
    inline_keyboard=[[cancel_button]]
)