import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "6"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# MMA лиги и их URL на ESPN
MMA_LEAGUES = {
    "UFC": {
        "url": "https://www.espn.com/mma/schedule/_/league/ufc",
        "emoji": "🥊",
        "name": "UFC"
    },
    "Bellator": {
        "url": "https://www.espn.com/mma/schedule/_/league/bellator",
        "emoji": "🔔",
        "name": "Bellator"
    },
    "PFL": {
        "url": "https://www.espn.com/mma/schedule/_/league/pfl",
        "emoji": "🏆",
        "name": "PFL"
    },
    "ONE": {
        "url": "https://www.espn.com/mma/schedule/_/league/one",
        "emoji": "☝️",
        "name": "ONE Championship"
    }
}

# Пути к файлам данных
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORAGE_FILE = os.path.join(DATA_DIR, "storage.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
