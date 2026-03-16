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
        "watch": ["ESPN+ (USA)", "UFC Fight Pass", "DAZN (EU)"],
        "official_url": "https://www.ufc.com/events"
    },
    "Bellator": {
        "url": "https://www.espn.com/mma/schedule/_/league/bellator",
        "emoji": "🔔",
        "name": "Bellator",
        "watch": ["CBS Sports", "Showtime", "DAZN"],
        "official_url": "https://www.bellator.com/events"
    },
    "PFL": {
        "url": "https://www.espn.com/mma/schedule/_/league/pfl",
        "emoji": "🏆",
        "name": "PFL",
        "watch": ["ESPN", "ESPN+", "DAZN"],
        "official_url": "https://www.pflmma.com/events"
    },
    "ONE": {
        "url": "https://www.espn.com/mma/schedule/_/league/one",
        "emoji": "☝️",
        "name": "ONE Championship",
        "watch": ["ONE YouTube", "Amazon Prime", "DAZN"],
        "official_url": "https://www.onefc.com/events"
    }
}

# Пути к файлам данных
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORAGE_FILE = os.path.join(DATA_DIR, "storage.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
