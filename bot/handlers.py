import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from services.mma_scraper import get_upcoming_events
from storage.json_storage import SubscriberStorage
from bot.keyboards import get_main_keyboard, get_event_inline_keyboard
from config import TIMEZONE, MMA_LEAGUES

logger = logging.getLogger(__name__)
router = Router()

# Инициализируем хранилище подписчиков
subscriber_storage = SubscriberStorage()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    leagues_list = ", ".join(MMA_LEAGUES.keys())
    welcome_text = (
        "👋 Привет! Я бот для отслеживания событий MMA.\n\n"
        "🥊 <b>Что я умею:</b>\n"
        f"• Показывать расписание событий: {leagues_list}\n"
        "• Отправлять уведомления о ближайших боях\n"
        "• Напоминать за 24 часа и 1 час до начала\n\n"
        "📋 <b>Команды:</b>\n"
        "/events — список ближайших событий\n"
        "/next — следующее событие с деталями\n"
        "/subscribe — подписаться на уведомления\n"
        "/unsubscribe — отписаться от уведомлений\n\n"
        "Выбери действие на клавиатуре ниже 👇"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("events"))
@router.message(F.text == "📅 Ближайшие события")
async def cmd_events(message: Message):
    """Показывает список ближайших событий."""
    await message.answer("🔄 Загружаю расписание событий со всех лиг...")

    try:
        events = await get_upcoming_events()

        if not events:
            await message.answer(
                "😔 Пока нет информации о предстоящих событиях.\n"
                "Попробуйте позже."
            )
            return

        # Показываем до 7 ближайших событий
        events_to_show = events[:7]

        response_lines = ["📅 <b>Ближайшие события MMA:</b>\n"]

        for event in events_to_show:
            response_lines.append(event.format_message(TIMEZONE))
            response_lines.append("")  # Пустая строка между событиями

        if len(events) > 7:
            response_lines.append(f"<i>...и ещё {len(events) - 7} событий</i>")

        await message.answer(
            "\n".join(response_lines),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при получении событий: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке событий.\n"
            "Попробуйте позже."
        )


@router.message(Command("next"))
@router.message(F.text == "🥊 Следующее событие")
async def cmd_next(message: Message):
    """Показывает следующее событие с деталями."""
    await message.answer("🔄 Загружаю информацию о следующем событии...")

    try:
        events = await get_upcoming_events()

        if not events:
            await message.answer(
                "😔 Пока нет информации о предстоящих событиях.\n"
                "Попробуйте позже."
            )
            return

        next_event = events[0]

        # Формируем расширенное сообщение
        message_text = next_event.format_message(TIMEZONE)

        # Добавляем информацию о времени до события
        hours = next_event.hours_until()
        if hours > 0:
            if hours < 1:
                time_text = f"⏰ До начала: менее часа!"
            elif hours < 24:
                time_text = f"⏰ До начала: {int(hours)} ч."
            else:
                days = int(hours / 24)
                remaining_hours = int(hours % 24)
                if remaining_hours > 0:
                    time_text = f"⏰ До начала: {days} дн. {remaining_hours} ч."
                else:
                    time_text = f"⏰ До начала: {days} дн."

            message_text = f"{message_text}\n\n{time_text}"

        keyboard = get_event_inline_keyboard(next_event.url) if next_event.url else None

        await message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при получении следующего события: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке события.\n"
            "Попробуйте позже."
        )


@router.message(Command("subscribe"))
@router.message(F.text == "🔔 Подписаться")
async def cmd_subscribe(message: Message):
    """Подписывает пользователя на уведомления."""
    chat_id = message.chat.id

    if subscriber_storage.add_subscriber(chat_id):
        leagues_list = ", ".join(MMA_LEAGUES.keys())
        await message.answer(
            "✅ Вы подписались на уведомления!\n\n"
            f"Лиги: {leagues_list}\n\n"
            "Вы будете получать:\n"
            "• Уведомления о новых событиях\n"
            "• Напоминание за 24 часа до начала\n"
            "• Напоминание за 1 час до начала"
        )
        logger.info(f"Новый подписчик: {chat_id}")
    else:
        await message.answer(
            "ℹ️ Вы уже подписаны на уведомления.\n\n"
            "Используйте /unsubscribe, чтобы отписаться."
        )


@router.message(Command("unsubscribe"))
@router.message(F.text == "🔕 Отписаться")
async def cmd_unsubscribe(message: Message):
    """Отписывает пользователя от уведомлений."""
    chat_id = message.chat.id

    if subscriber_storage.remove_subscriber(chat_id):
        await message.answer(
            "🔕 Вы отписались от уведомлений.\n\n"
            "Используйте /subscribe, чтобы подписаться снова."
        )
        logger.info(f"Отписка: {chat_id}")
    else:
        await message.answer(
            "ℹ️ Вы не были подписаны на уведомления.\n\n"
            "Используйте /subscribe, чтобы подписаться."
        )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Показывает статус подписки пользователя."""
    chat_id = message.chat.id
    is_subscribed = subscriber_storage.is_subscribed(chat_id)

    if is_subscribed:
        await message.answer("✅ Вы подписаны на уведомления.")
    else:
        await message.answer(
            "❌ Вы не подписаны на уведомления.\n"
            "Используйте /subscribe, чтобы подписаться."
        )
