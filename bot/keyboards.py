from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import MMA_LEAGUES, REGION_NAMES


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Events"), KeyboardButton(text="⏱ Countdown")],
            [KeyboardButton(text="🥊 UFC"), KeyboardButton(text="🏆 PFL"), KeyboardButton(text="🔔 Bellator")],
            [KeyboardButton(text="⚙️ Settings")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_event_inline_keyboard(event_url: str = None, event_id: str = None) -> InlineKeyboardMarkup:
    """Inline клавиатура для события."""
    buttons = []

    if event_id:
        buttons.append([InlineKeyboardButton(text="📅 Add to Calendar", callback_data=f"ics:{event_id}")])

    if event_url:
        buttons.append([InlineKeyboardButton(text="🔗 More Info", url=event_url)])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def get_settings_keyboard(current_leagues: list[str], current_region: str) -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    buttons = []

    # Лиги
    buttons.append([InlineKeyboardButton(text="📋 Leagues:", callback_data="noop")])

    league_row = []
    for league_key, league_info in MMA_LEAGUES.items():
        emoji = league_info["emoji"]
        check = "✅" if league_key in current_leagues else "❌"
        league_row.append(InlineKeyboardButton(
            text=f"{check} {emoji} {league_key}",
            callback_data=f"toggle_league:{league_key}"
        ))
    buttons.append(league_row)

    # Регион
    buttons.append([InlineKeyboardButton(text="🌍 Region:", callback_data="noop")])

    region_row = []
    for region_code, region_name in REGION_NAMES.items():
        check = "✅" if region_code == current_region else ""
        region_row.append(InlineKeyboardButton(
            text=f"{check} {region_name}",
            callback_data=f"set_region:{region_code}"
        ))
    buttons.append(region_row)

    # Закрыть
    buttons.append([InlineKeyboardButton(text="✖️ Close", callback_data="close_settings")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_region_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора региона."""
    buttons = []

    for region_code, region_name in REGION_NAMES.items():
        buttons.append([InlineKeyboardButton(
            text=region_name,
            callback_data=f"set_region:{region_code}"
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
