import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "6"))
TIMEZONE = os.getenv("TIMEZONE", "CET")

# MMA лиги и их URL на ESPN
MMA_LEAGUES = {
    "UFC": {
        "url": "https://www.espn.com/mma/schedule/_/league/ufc",
        "emoji": "🥊",
        "name": "UFC",
        "official_url": "https://www.ufc.com/events"
    },
    "Bellator": {
        "url": "https://www.espn.com/mma/schedule/_/league/bellator",
        "emoji": "🔔",
        "name": "Bellator",
        "official_url": "https://www.bellator.com/events"
    },
    "PFL": {
        "url": "https://www.espn.com/mma/schedule/_/league/pfl",
        "emoji": "🏆",
        "name": "PFL",
        "official_url": "https://www.pflmma.com/events"
    }
}

# Стриминг по регионам
STREAMING_BY_REGION = {
    "US": {
        "UFC": ["ESPN+", "ABC", "ESPN"],
        "Bellator": ["CBS Sports", "Showtime"],
        "PFL": ["ESPN", "ESPN+"]
    },
    "DE": {
        "UFC": ["DAZN"],
        "Bellator": ["DAZN"],
        "PFL": ["DAZN"]
    },
    "RU": {
        "UFC": ["Okko", "Матч ТВ"],
        "Bellator": ["Матч ТВ"],
        "PFL": ["Матч ТВ"]
    }
}

# Таймзоны по регионам
TIMEZONE_BY_REGION = {
    "US": "America/New_York",
    "DE": "Europe/Berlin",
    "RU": "Europe/Moscow"
}

# Названия регионов
REGION_NAMES = {
    "US": "🇺🇸 USA",
    "DE": "🇩🇪 Germany",
    "RU": "🇷🇺 Russia"
}

# Пути к файлам данных
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORAGE_FILE = os.path.join(DATA_DIR, "storage.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
