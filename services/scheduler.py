import logging
import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from services.mma_scraper import get_upcoming_events
from storage.json_storage import NotificationStorage, SubscriberStorage
from models.event import Event
from config import CHECK_INTERVAL_HOURS, TIMEZONE

logger = logging.getLogger(__name__)


class EventScheduler:
    """Планировщик проверки событий и отправки уведомлений."""

    # Типы уведомлений
    NOTIFICATION_NEW = "new"
    NOTIFICATION_24H = "24h"
    NOTIFICATION_1H = "1h"

    def __init__(
        self,
        send_message: Callable[[int, str], Awaitable[None]],
        notification_storage: NotificationStorage = None,
        subscriber_storage: SubscriberStorage = None
    ):
        """
        Args:
            send_message: Асинхронная функция для отправки сообщений (chat_id, text)
            notification_storage: Хранилище уведомлений
            subscriber_storage: Хранилище подписчиков
        """
        self.send_message = send_message
        self.notification_storage = notification_storage or NotificationStorage()
        self.subscriber_storage = subscriber_storage or SubscriberStorage()
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        self._cached_events: list[Event] = []

    async def start(self):
        """Запускает планировщик."""
        # Проверка событий каждые N часов
        self.scheduler.add_job(
            self.check_events,
            trigger=IntervalTrigger(hours=CHECK_INTERVAL_HOURS),
            id="check_events",
            replace_existing=True
        )

        # Проверка напоминаний каждые 15 минут
        self.scheduler.add_job(
            self.check_reminders,
            trigger=IntervalTrigger(minutes=15),
            id="check_reminders",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Планировщик запущен (проверка каждые {CHECK_INTERVAL_HOURS} ч.)")

        # Первая проверка при запуске
        await self.check_events()

    def stop(self):
        """Останавливает планировщик."""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")

    async def check_events(self):
        """Проверяет новые события и отправляет уведомления."""
        logger.info("Проверка новых событий...")

        try:
            events = await get_upcoming_events()
            self._cached_events = events

            if not events:
                logger.info("Событий не найдено")
                return

            subscribers = self.subscriber_storage.get_all_subscribers()
            if not subscribers:
                logger.info("Нет подписчиков для уведомлений")
                self.notification_storage.update_last_check()
                return

            # Проверяем каждое событие на новизну
            for event in events:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_NEW):
                    await self._send_new_event_notification(event, subscribers)

            # Обновляем время проверки и чистим старые записи
            self.notification_storage.update_last_check()
            current_ids = {e.id for e in events}
            self.notification_storage.cleanup_old_events(current_ids)

        except Exception as e:
            logger.error(f"Ошибка при проверке событий: {e}")

    async def check_reminders(self):
        """Проверяет события и отправляет напоминания за 24ч и 1ч."""
        if not self._cached_events:
            # Если кэш пуст, загружаем события
            try:
                self._cached_events = await get_upcoming_events()
            except Exception as e:
                logger.error(f"Ошибка загрузки событий для напоминаний: {e}")
                return

        subscribers = self.subscriber_storage.get_all_subscribers()
        if not subscribers:
            return

        for event in self._cached_events:
            hours = event.hours_until()

            # Напоминание за 24 часа (между 24 и 23.75 часами)
            if 23.75 <= hours <= 24.25:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_24H):
                    await self._send_reminder(event, subscribers, "24 часа", self.NOTIFICATION_24H)

            # Напоминание за 1 час (между 1 и 0.75 часами)
            elif 0.75 <= hours <= 1.25:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_1H):
                    await self._send_reminder(event, subscribers, "1 час", self.NOTIFICATION_1H)

    async def _send_new_event_notification(self, event: Event, subscribers: list[int]):
        """Отправляет уведомление о новом событии."""
        message = (
            f"🆕 <b>Новое событие {event.league}!</b>\n\n"
            f"{event.format_message(TIMEZONE)}"
        )

        success_count = await self._broadcast(message, subscribers)
        logger.info(f"Уведомление о новом событии '{event.name}' отправлено {success_count}/{len(subscribers)} подписчикам")

        self.notification_storage.mark_notified(event.id, self.NOTIFICATION_NEW)

    async def _send_reminder(self, event: Event, subscribers: list[int], time_text: str, notification_type: str):
        """Отправляет напоминание о событии."""
        emoji = "⏰" if notification_type == self.NOTIFICATION_24H else "🔔"

        message = (
            f"{emoji} <b>Напоминание: до события осталось {time_text}!</b>\n\n"
            f"{event.format_message(TIMEZONE)}"
        )

        success_count = await self._broadcast(message, subscribers)
        logger.info(f"Напоминание ({time_text}) о '{event.name}' отправлено {success_count}/{len(subscribers)} подписчикам")

        self.notification_storage.mark_notified(event.id, notification_type)

    async def _broadcast(self, message: str, chat_ids: list[int]) -> int:
        """Отправляет сообщение всем подписчикам."""
        success_count = 0

        for chat_id in chat_ids:
            try:
                await self.send_message(chat_id, message)
                success_count += 1
                # Небольшая задержка, чтобы не превышать лимиты Telegram
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения {chat_id}: {e}")
                # Если пользователь заблокировал бота, удаляем его
                if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                    self.subscriber_storage.remove_subscriber(chat_id)
                    logger.info(f"Подписчик {chat_id} удалён (заблокировал бота)")

        return success_count

    def get_cached_events(self) -> list[Event]:
        """Возвращает кэшированные события."""
        return self._cached_events.copy()
