import logging
import io
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from services.mma_scraper import get_upcoming_events
from storage.json_storage import SubscriberStorage, ALL_LEAGUES
from bot.keyboards import (
    get_main_keyboard, get_event_inline_keyboard,
    get_settings_keyboard, get_region_keyboard
)
from config import MMA_LEAGUES, REGION_NAMES

logger = logging.getLogger(__name__)
router = Router()

# Инициализируем хранилище подписчиков
subscriber_storage = SubscriberStorage()


# === Основные команды ===

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    chat_id = message.chat.id

    # Добавляем пользователя, если его нет
    if not subscriber_storage.is_subscribed(chat_id):
        subscriber_storage.add_subscriber(chat_id)

        # Предлагаем выбрать регион
        await message.answer(
            "👋 Welcome to MMA Events Bot!\n\n"
            "🌍 Please select your region for correct times and streaming info:",
            reply_markup=get_region_keyboard()
        )
    else:
        region = subscriber_storage.get_region(chat_id)
        region_name = REGION_NAMES.get(region, region)

        leagues = subscriber_storage.get_leagues(chat_id)
        leagues_str = ", ".join(leagues) if leagues else "None"

        welcome_text = (
            "👋 Welcome back to MMA Events Bot!\n\n"
            f"🌍 Region: {region_name}\n"
            f"📋 Tracking: {leagues_str}\n\n"
            "🥊 <b>Commands:</b>\n"
            "/events — all upcoming events\n"
            "/ufc /pfl /bellator — events by league\n"
            "/countdown — next event countdown\n"
            "/settings — notification settings\n"
            "/subscribe /unsubscribe — notifications\n\n"
            "Use buttons below 👇"
        )

        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )


# === События по лигам ===

@router.message(Command("events"))
@router.message(F.text == "📅 Events")
async def cmd_events(message: Message):
    """Показывает все ближайшие события."""
    await show_events(message, leagues=None)


@router.message(Command("ufc"))
@router.message(F.text == "🥊 UFC")
async def cmd_ufc(message: Message):
    """Показывает только UFC события."""
    await show_events(message, leagues=["UFC"])


@router.message(Command("pfl"))
@router.message(F.text == "🏆 PFL")
async def cmd_pfl(message: Message):
    """Показывает только PFL события."""
    await show_events(message, leagues=["PFL"])


@router.message(Command("bellator"))
@router.message(F.text == "🔔 Bellator")
async def cmd_bellator(message: Message):
    """Показывает только Bellator события."""
    await show_events(message, leagues=["Bellator"])


async def show_events(message: Message, leagues: list[str] = None):
    """Показывает события с фильтрацией по лигам."""
    chat_id = message.chat.id
    region = subscriber_storage.get_region(chat_id)

    league_name = leagues[0] if leagues and len(leagues) == 1 else "MMA"
    await message.answer(f"🔄 Loading {league_name} events...")

    try:
        events = await get_upcoming_events(leagues=leagues)

        if not events:
            await message.answer(
                f"😔 No upcoming {league_name} events found.\n"
                "Try again later."
            )
            return

        events_to_show = events[:7]

        header = f"📅 <b>Upcoming {league_name} Events:</b>\n"
        response_lines = [header]

        for event in events_to_show:
            response_lines.append(event.format_message(region))
            response_lines.append("")

        if len(events) > 7:
            response_lines.append(f"<i>...and {len(events) - 7} more</i>")

        await message.answer(
            "\n".join(response_lines),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        await message.answer("❌ Error loading events. Try again later.")


# === Countdown ===

@router.message(Command("countdown"))
@router.message(Command("next"))
@router.message(F.text == "⏱ Countdown")
async def cmd_countdown(message: Message):
    """Показывает countdown до следующего события."""
    chat_id = message.chat.id
    region = subscriber_storage.get_region(chat_id)
    user_leagues = subscriber_storage.get_leagues(chat_id)

    await message.answer("🔄 Loading next event...")

    try:
        events = await get_upcoming_events(leagues=user_leagues if user_leagues else None)

        if not events:
            await message.answer("😔 No upcoming events found.")
            return

        next_event = events[0]

        # Формируем сообщение
        countdown = next_event.format_countdown()
        event_msg = next_event.format_message(region)

        message_text = f"{countdown}\n\n{event_msg}"

        # Клавиатура с календарём
        keyboard = get_event_inline_keyboard(
            event_url=next_event.url,
            event_id=next_event.id
        )

        await message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error in countdown: {e}")
        await message.answer("❌ Error loading event. Try again later.")


# === Calendar ICS ===

@router.callback_query(F.data.startswith("ics:"))
async def callback_ics(callback: CallbackQuery):
    """Генерирует и отправляет ICS файл."""
    event_id = callback.data.split(":")[1]
    chat_id = callback.message.chat.id
    user_leagues = subscriber_storage.get_leagues(chat_id)

    try:
        events = await get_upcoming_events(leagues=user_leagues if user_leagues else None)

        # Ищем событие по ID
        event = next((e for e in events if e.id == event_id), None)

        if not event:
            await callback.answer("Event not found", show_alert=True)
            return

        # Генерируем ICS
        ics_content = event.generate_ics()

        # Отправляем как файл
        file = BufferedInputFile(
            ics_content.encode('utf-8'),
            filename=f"{event.name.replace(' ', '_')}.ics"
        )

        await callback.message.answer_document(
            file,
            caption=f"📅 Calendar event: {event.name}"
        )

        await callback.answer("Calendar file sent!")

    except Exception as e:
        logger.error(f"Error generating ICS: {e}")
        await callback.answer("Error generating calendar file", show_alert=True)


# === Settings ===

@router.message(Command("settings"))
@router.message(F.text == "⚙️ Settings")
async def cmd_settings(message: Message):
    """Показывает настройки."""
    chat_id = message.chat.id

    if not subscriber_storage.is_subscribed(chat_id):
        subscriber_storage.add_subscriber(chat_id)

    current_leagues = subscriber_storage.get_leagues(chat_id)
    current_region = subscriber_storage.get_region(chat_id)

    await message.answer(
        "⚙️ <b>Settings</b>\n\n"
        "Select leagues to track and your region:",
        reply_markup=get_settings_keyboard(current_leagues, current_region),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("toggle_league:"))
async def callback_toggle_league(callback: CallbackQuery):
    """Переключает лигу."""
    league = callback.data.split(":")[1]
    chat_id = callback.message.chat.id

    if not subscriber_storage.is_subscribed(chat_id):
        subscriber_storage.add_subscriber(chat_id)

    new_state = subscriber_storage.toggle_league(chat_id, league)

    # Обновляем клавиатуру
    current_leagues = subscriber_storage.get_leagues(chat_id)
    current_region = subscriber_storage.get_region(chat_id)

    status = "enabled" if new_state else "disabled"
    await callback.answer(f"{league} notifications {status}")

    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(current_leagues, current_region)
    )


@router.callback_query(F.data.startswith("set_region:"))
async def callback_set_region(callback: CallbackQuery):
    """Устанавливает регион."""
    region = callback.data.split(":")[1]
    chat_id = callback.message.chat.id

    if not subscriber_storage.is_subscribed(chat_id):
        subscriber_storage.add_subscriber(chat_id)

    subscriber_storage.set_region(chat_id, region)
    region_name = REGION_NAMES.get(region, region)

    await callback.answer(f"Region set to {region_name}")

    # Проверяем, это первый запуск или настройки
    if "select your region" in callback.message.text.lower():
        # Первый запуск — показываем welcome
        current_leagues = subscriber_storage.get_leagues(chat_id)
        leagues_str = ", ".join(current_leagues)

        await callback.message.edit_text(
            f"✅ Region set to {region_name}\n\n"
            f"📋 Tracking: {leagues_str}\n\n"
            "You're all set! Use /events to see upcoming fights.",
            parse_mode="HTML"
        )

        await callback.message.answer(
            "Use buttons below 👇",
            reply_markup=get_main_keyboard()
        )
    else:
        # Настройки — обновляем клавиатуру
        current_leagues = subscriber_storage.get_leagues(chat_id)
        await callback.message.edit_reply_markup(
            reply_markup=get_settings_keyboard(current_leagues, region)
        )


@router.callback_query(F.data == "close_settings")
async def callback_close_settings(callback: CallbackQuery):
    """Закрывает настройки."""
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """Ничего не делает."""
    await callback.answer()


# === Подписка ===

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    """Подписывает пользователя на уведомления."""
    chat_id = message.chat.id

    if subscriber_storage.add_subscriber(chat_id):
        await message.answer(
            "✅ Subscribed to notifications!\n\n"
            "Use /settings to customize leagues and region."
        )
        logger.info(f"New subscriber: {chat_id}")
    else:
        await message.answer(
            "ℹ️ You're already subscribed.\n\n"
            "Use /settings to customize or /unsubscribe to stop."
        )


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    """Отписывает пользователя от уведомлений."""
    chat_id = message.chat.id

    if subscriber_storage.remove_subscriber(chat_id):
        await message.answer(
            "🔕 Unsubscribed from notifications.\n\n"
            "Use /subscribe to resubscribe."
        )
        logger.info(f"Unsubscribed: {chat_id}")
    else:
        await message.answer(
            "ℹ️ You weren't subscribed.\n\n"
            "Use /subscribe to subscribe."
        )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Показывает статус подписки пользователя."""
    chat_id = message.chat.id

    if subscriber_storage.is_subscribed(chat_id):
        leagues = subscriber_storage.get_leagues(chat_id)
        region = subscriber_storage.get_region(chat_id)
        region_name = REGION_NAMES.get(region, region)

        leagues_str = ", ".join(leagues) if leagues else "None"

        await message.answer(
            "✅ <b>Subscribed</b>\n\n"
            f"🌍 Region: {region_name}\n"
            f"📋 Leagues: {leagues_str}\n\n"
            "Use /settings to change.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Not subscribed.\n"
            "Use /subscribe to subscribe."
        )
