import json
import os
from datetime import datetime
from typing import Set

from config import DATA_DIR, STORAGE_FILE, SUBSCRIBERS_FILE, MMA_LEAGUES


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


# Все доступные лиги
ALL_LEAGUES = list(MMA_LEAGUES.keys())

# Поддерживаемые регионы
SUPPORTED_REGIONS = ["US", "DE", "RU"]
DEFAULT_REGION = "US"


class SubscriberStorage:
    """Хранилище подписчиков на уведомления."""

    def __init__(self, filepath: str = SUBSCRIBERS_FILE):
        self.filepath = filepath
        ensure_data_dir()
        self._load()
        self._migrate_if_needed()

    def _load(self):
        """Загружает данные из файла."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "subscribers": {}  # chat_id -> {leagues: [...], region: "US"}
            }

    def _migrate_if_needed(self):
        """Мигрирует старый формат (список) в новый (словарь)."""
        if isinstance(self.data.get("subscribers"), list):
            old_list = self.data["subscribers"]
            self.data["subscribers"] = {}
            for chat_id in old_list:
                self.data["subscribers"][str(chat_id)] = {
                    "leagues": ALL_LEAGUES.copy(),
                    "region": DEFAULT_REGION
                }
            self._save()

    def _save(self):
        """Сохраняет данные в файл."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def _get_subscriber(self, chat_id: int) -> dict | None:
        """Возвращает данные подписчика."""
        return self.data["subscribers"].get(str(chat_id))

    def add_subscriber(self, chat_id: int, leagues: list[str] = None, region: str = None) -> bool:
        """Добавляет подписчика. Возвращает True если добавлен, False если уже был."""
        key = str(chat_id)
        if key not in self.data["subscribers"]:
            self.data["subscribers"][key] = {
                "leagues": leagues or ALL_LEAGUES.copy(),
                "region": region or DEFAULT_REGION
            }
            self._save()
            return True
        return False

    def remove_subscriber(self, chat_id: int) -> bool:
        """Удаляет подписчика. Возвращает True если удалён, False если не был подписан."""
        key = str(chat_id)
        if key in self.data["subscribers"]:
            del self.data["subscribers"][key]
            self._save()
            return True
        return False

    def is_subscribed(self, chat_id: int) -> bool:
        """Проверяет, подписан ли пользователь."""
        return str(chat_id) in self.data["subscribers"]

    def get_all_subscribers(self) -> list[int]:
        """Возвращает список всех подписчиков."""
        return [int(chat_id) for chat_id in self.data["subscribers"].keys()]

    def get_subscribers_for_league(self, league: str) -> list[int]:
        """Возвращает подписчиков, которые следят за конкретной лигой."""
        result = []
        for chat_id, data in self.data["subscribers"].items():
            if league in data.get("leagues", ALL_LEAGUES):
                result.append(int(chat_id))
        return result

    # === Leagues ===

    def get_leagues(self, chat_id: int) -> list[str]:
        """Возвращает список лиг пользователя."""
        sub = self._get_subscriber(chat_id)
        if sub:
            return sub.get("leagues", ALL_LEAGUES.copy())
        return ALL_LEAGUES.copy()

    def set_leagues(self, chat_id: int, leagues: list[str]):
        """Устанавливает список лиг для пользователя."""
        key = str(chat_id)
        if key in self.data["subscribers"]:
            self.data["subscribers"][key]["leagues"] = leagues
            self._save()

    def toggle_league(self, chat_id: int, league: str) -> bool:
        """Переключает лигу. Возвращает новое состояние (True = включена)."""
        key = str(chat_id)
        if key not in self.data["subscribers"]:
            return False

        leagues = self.data["subscribers"][key].get("leagues", ALL_LEAGUES.copy())

        if league in leagues:
            leagues.remove(league)
            new_state = False
        else:
            leagues.append(league)
            new_state = True

        self.data["subscribers"][key]["leagues"] = leagues
        self._save()
        return new_state

    # === Region ===

    def get_region(self, chat_id: int) -> str:
        """Возвращает регион пользователя."""
        sub = self._get_subscriber(chat_id)
        if sub:
            return sub.get("region", DEFAULT_REGION)
        return DEFAULT_REGION

    def set_region(self, chat_id: int, region: str) -> bool:
        """Устанавливает регион для пользователя."""
        if region not in SUPPORTED_REGIONS:
            return False

        key = str(chat_id)
        if key in self.data["subscribers"]:
            self.data["subscribers"][key]["region"] = region
            self._save()
            return True
        return False
