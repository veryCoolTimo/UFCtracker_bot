import logging
import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.mma_scraper import get_upcoming_events
from storage.json_storage import NotificationStorage, SubscriberStorage
from models.event import Event
from config import CHECK_INTERVAL_HOURS, TIMEZONE

logger = logging.getLogger(__name__)


class EventScheduler:
    """Планировщик проверки событий и отправки уведомлений."""

    NOTIFICATION_NEW = "new"
    NOTIFICATION_24H = "24h"
    NOTIFICATION_1H = "1h"

    def __init__(
        self,
        send_message: Callable[[int, str], Awaitable[None]],
        notification_storage: NotificationStorage = None,
        subscriber_storage: SubscriberStorage = None
    ):
        self.send_message = send_message
        self.notification_storage = notification_storage or NotificationStorage()
        self.subscriber_storage = subscriber_storage or SubscriberStorage()
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        self._cached_events: list[Event] = []

    async def start(self):
        """Запускает планировщик."""
        self.scheduler.add_job(
            self.check_events,
            trigger=IntervalTrigger(hours=CHECK_INTERVAL_HOURS),
            id="check_events",
            replace_existing=True
        )

        self.scheduler.add_job(
            self.check_reminders,
            trigger=IntervalTrigger(minutes=15),
            id="check_reminders",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Scheduler started (checking every {CHECK_INTERVAL_HOURS}h)")

        await self.check_events()

    def stop(self):
        """Останавливает планировщик."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def check_events(self):
        """Проверяет новые события и отправляет уведомления."""
        logger.info("Checking for new events...")

        try:
            events = await get_upcoming_events()
            self._cached_events = events

            if not events:
                logger.info("No events found")
                return

            # Проверяем каждое событие на новизну
            for event in events:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_NEW):
                    # Получаем подписчиков для этой лиги
                    subscribers = self.subscriber_storage.get_subscribers_for_league(event.league)
                    if subscribers:
                        await self._send_new_event_notification(event, subscribers)

            self.notification_storage.update_last_check()
            current_ids = {e.id for e in events}
            self.notification_storage.cleanup_old_events(current_ids)

        except Exception as e:
            logger.error(f"Error checking events: {e}")

    async def check_reminders(self):
        """Проверяет события и отправляет напоминания за 24ч и 1ч."""
        if not self._cached_events:
            try:
                self._cached_events = await get_upcoming_events()
            except Exception as e:
                logger.error(f"Error loading events for reminders: {e}")
                return

        for event in self._cached_events:
            hours = event.hours_until()

            # Напоминание за 24 часа
            if 23.75 <= hours <= 24.25:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_24H):
                    subscribers = self.subscriber_storage.get_subscribers_for_league(event.league)
                    if subscribers:
                        await self._send_reminder(event, subscribers, "24 hours", self.NOTIFICATION_24H)

            # Напоминание за 1 час
            elif 0.75 <= hours <= 1.25:
                if not self.notification_storage.is_notified(event.id, self.NOTIFICATION_1H):
                    subscribers = self.subscriber_storage.get_subscribers_for_league(event.league)
                    if subscribers:
                        await self._send_reminder(event, subscribers, "1 hour", self.NOTIFICATION_1H)

    async def _send_new_event_notification(self, event: Event, subscribers: list[int]):
        """Отправляет уведомление о новом событии."""
        success_count = 0

        for chat_id in subscribers:
            region = self.subscriber_storage.get_region(chat_id)
            message = (
                f"🆕 <b>New {event.league} Event!</b>\n\n"
                f"{event.format_message(region)}"
            )

            try:
                await self.send_message(chat_id, message)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error sending to {chat_id}: {e}")
                if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                    self.subscriber_storage.remove_subscriber(chat_id)

        logger.info(f"New event '{event.name}' sent to {success_count}/{len(subscribers)}")
        self.notification_storage.mark_notified(event.id, self.NOTIFICATION_NEW)

    async def _send_reminder(self, event: Event, subscribers: list[int], time_text: str, notification_type: str):
        """Отправляет напоминание о событии."""
        emoji = "⏰" if notification_type == self.NOTIFICATION_24H else "🔔"
        success_count = 0

        for chat_id in subscribers:
            region = self.subscriber_storage.get_region(chat_id)
            message = (
                f"{emoji} <b>Reminder: {time_text} until event!</b>\n\n"
                f"{event.format_message(region)}"
            )

            try:
                await self.send_message(chat_id, message)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error sending to {chat_id}: {e}")
                if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                    self.subscriber_storage.remove_subscriber(chat_id)

        logger.info(f"Reminder ({time_text}) for '{event.name}' sent to {success_count}/{len(subscribers)}")
        self.notification_storage.mark_notified(event.id, notification_type)

    def get_cached_events(self) -> list[Event]:
        """Возвращает кэшированные события."""
        return self._cached_events.copy()
