import json
import os
from datetime import datetime
from typing import Set

from config import DATA_DIR, STORAGE_FILE, SUBSCRIBERS_FILE


def ensure_data_dir():
    """Создаёт директорию для данных, если её нет."""
    os.makedirs(DATA_DIR, exist_ok=True)


class NotificationStorage:
    """Хранилище для отслеживания отправленных уведомлений."""

    def __init__(self, filepath: str = STORAGE_FILE):
        self.filepath = filepath
        ensure_data_dir()
        self._load()

    def _load(self):
        """Загружает данные из файла."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "notified_events": {},  # event_id -> list of notification types sent
                "last_check": None
            }

    def _save(self):
        """Сохраняет данные в файл."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_notified(self, event_id: str, notification_type: str) -> bool:
        """Проверяет, было ли отправлено уведомление."""
        notifications = self.data["notified_events"].get(event_id, [])
        return notification_type in notifications

    def mark_notified(self, event_id: str, notification_type: str):
        """Помечает уведомление как отправленное."""
        if event_id not in self.data["notified_events"]:
            self.data["notified_events"][event_id] = []
        if notification_type not in self.data["notified_events"][event_id]:
            self.data["notified_events"][event_id].append(notification_type)
        self._save()

    def update_last_check(self):
        """Обновляет время последней проверки."""
        self.data["last_check"] = datetime.now().isoformat()
        self._save()

    def get_last_check(self) -> datetime | None:
        """Возвращает время последней проверки."""
        if self.data["last_check"]:
            return datetime.fromisoformat(self.data["last_check"])
        return None

    def cleanup_old_events(self, current_event_ids: Set[str]):
        """Удаляет записи о старых событиях."""
        old_ids = set(self.data["notified_events"].keys()) - current_event_ids
        for event_id in old_ids:
            del self.data["notified_events"][event_id]
        if old_ids:
            self._save()


class SubscriberStorage:
    """Хранилище подписчиков на уведомления."""

    def __init__(self, filepath: str = SUBSCRIBERS_FILE):
        self.filepath = filepath
        ensure_data_dir()
        self._load()

    def _load(self):
        """Загружает данные из файла."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "subscribers": []  # list of chat_ids
            }

    def _save(self):
        """Сохраняет данные в файл."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_subscriber(self, chat_id: int) -> bool:
        """Добавляет подписчика. Возвращает True если добавлен, False если уже был."""
        if chat_id not in self.data["subscribers"]:
            self.data["subscribers"].append(chat_id)
            self._save()
            return True
        return False

    def remove_subscriber(self, chat_id: int) -> bool:
        """Удаляет подписчика. Возвращает True если удалён, False если не был подписан."""
        if chat_id in self.data["subscribers"]:
            self.data["subscribers"].remove(chat_id)
            self._save()
            return True
        return False

    def is_subscribed(self, chat_id: int) -> bool:
        """Проверяет, подписан ли пользователь."""
        return chat_id in self.data["subscribers"]

    def get_all_subscribers(self) -> list[int]:
        """Возвращает список всех подписчиков."""
        return self.data["subscribers"].copy()
