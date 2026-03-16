from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Ближайшие события"), KeyboardButton(text="🥊 Следующее событие")],
            [KeyboardButton(text="🔔 Подписаться"), KeyboardButton(text="🔕 Отписаться")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_event_inline_keyboard(event_url: str = None) -> InlineKeyboardMarkup:
    """Inline клавиатура для события."""
    buttons = []

    if event_url:
        buttons.append([InlineKeyboardButton(text="🔗 Подробнее", url=event_url)])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
