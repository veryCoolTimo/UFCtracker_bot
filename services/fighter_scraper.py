import aiohttp
import logging
import re
import json
import os
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import quote

from config import DATA_DIR

logger = logging.getLogger(__name__)

# Кэш файл для бойцов
FIGHTER_CACHE_FILE = os.path.join(DATA_DIR, "fighters_cache.json")


@dataclass
class Fighter:
    name: str
    record: str  # "26-1-0"
    wins: int = 0
    losses: int = 0
    draws: int = 0
    nickname: str = ""
    weight_class: str = ""
    rank: str = ""  # "#1" or "C" for champion
    photo_url: str = ""
    height: str = ""
    reach: str = ""
    age: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Fighter":
        return cls(**data)

    @property
    def short_record(self) -> str:
        """Возвращает короткий рекорд (26-1)"""
        if self.draws > 0:
            return f"{self.wins}-{self.losses}-{self.draws}"
        return f"{self.wins}-{self.losses}"


class FighterCache:
    """Кэш данных о бойцах."""

    def __init__(self):
        self.cache: dict[str, dict] = {}
        self._load()

    def _load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(FIGHTER_CACHE_FILE):
            try:
                with open(FIGHTER_CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading fighter cache: {e}")
                self.cache = {}

    def _save(self):
        with open(FIGHTER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, name: str) -> Optional[Fighter]:
        key = name.lower().strip()
        if key in self.cache:
            return Fighter.from_dict(self.cache[key])
        return None

    def set(self, fighter: Fighter):
        key = fighter.name.lower().strip()
        self.cache[key] = fighter.to_dict()
        self._save()

    def clear(self):
        """Очищает кэш."""
        self.cache = {}
        self._save()


# Глобальный кэш
fighter_cache = FighterCache()


class FighterScraper:
    """Парсер данных о бойцах."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.HEADERS)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_fighter(self, name: str) -> Optional[Fighter]:
        """Получает данные бойца (из кэша или парсит)."""
        # Проверяем кэш
        cached = fighter_cache.get(name)
        if cached and cached.photo_url:  # Только если есть фото
            return cached

        # Парсим с UFCStats
        fighter = await self._search_ufcstats(name)

        if fighter:
            # Получаем фото с Sherdog
            fighter.photo_url = await self._get_fighter_photo(name)

            fighter_cache.set(fighter)
            return fighter

        return None

    async def _search_ufcstats(self, name: str) -> Optional[Fighter]:
        """Ищет бойца на UFCStats."""
        if not self.session:
            return None

        try:
            # Try full name first, then first name only
            search_terms = [name]
            if " " in name:
                search_terms.append(name.split()[0])  # First name

            for term in search_terms:
                search_url = f"http://ufcstats.com/statistics/fighters/search?query={quote(term)}"
                async with self.session.get(search_url) as response:
                    if response.status != 200:
                        continue

                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")

                    # Find links to fighter detail pages
                    all_links = soup.select("a.b-link_style_black")
                    for link in all_links:
                        href = link.get("href", "")
                        if "fighter-details" in href:
                            return await self._parse_fighter_page(href)

            return None

        except Exception as e:
            logger.error(f"Error searching UFCStats for {name}: {e}")
            return None

    async def _parse_fighter_page(self, url: str) -> Optional[Fighter]:
        """Парсит страницу бойца на UFCStats."""
        if not self.session:
            return None

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                name_elem = soup.select_one("span.b-content__title-highlight")
                if not name_elem:
                    return None
                name = name_elem.get_text(strip=True)

                nickname = ""
                nick_elem = soup.select_one("p.b-content__Nickname")
                if nick_elem:
                    nickname = nick_elem.get_text(strip=True).strip('"')

                record_elem = soup.select_one("span.b-content__title-record")
                record = "0-0-0"
                wins, losses, draws = 0, 0, 0

                if record_elem:
                    record_text = record_elem.get_text(strip=True)
                    match = re.search(r"(\d+)-(\d+)-(\d+)", record_text)
                    if match:
                        wins = int(match.group(1))
                        losses = int(match.group(2))
                        draws = int(match.group(3))
                        record = f"{wins}-{losses}-{draws}"

                height = ""
                reach = ""
                weight_class = ""

                details = soup.select("li.b-list__box-list-item")
                for detail in details:
                    text = detail.get_text(strip=True)
                    if "Height:" in text:
                        height = text.replace("Height:", "").strip()
                    elif "Reach:" in text:
                        reach = text.replace("Reach:", "").strip()
                    elif "Weight:" in text:
                        weight_class = text.replace("Weight:", "").strip()

                return Fighter(
                    name=name,
                    record=record,
                    wins=wins,
                    losses=losses,
                    draws=draws,
                    nickname=nickname,
                    weight_class=weight_class,
                    height=height,
                    reach=reach
                )

        except Exception as e:
            logger.error(f"Error parsing fighter page: {e}")
            return None

    async def _get_fighter_photo(self, name: str) -> str:
        """Получает URL фото бойца с Sherdog."""
        if not self.session:
            return ""

        try:
            # Поиск бойца на Sherdog
            search_url = f"https://www.sherdog.com/stats/fightfinder?SearchTxt={quote(name)}"

            async with self.session.get(search_url, allow_redirects=True) as response:
                if response.status != 200:
                    return ""

                html = await response.text()

                # Ищем ссылку на страницу бойца
                last_name = name.split()[-1].lower()
                pattern = rf'/fighter/[^"\']+{last_name}[^"\'\s]*'
                match = re.search(pattern, html, re.IGNORECASE)

                if not match:
                    logger.debug(f"Fighter {name} not found on Sherdog")
                    return ""

                fighter_path = match.group(0)
                fighter_url = f"https://www.sherdog.com{fighter_path}"

                # Получаем страницу бойца
                async with self.session.get(fighter_url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        return ""

                    fighter_html = await resp.text()

                    # Способ 1: og:image meta tag
                    og_match = re.search(r'og:image"\s+content="([^"]+_images/fighter/[^"]+\.(?:jpg|png|JPG|PNG))"', fighter_html)
                    if og_match:
                        photo_path = og_match.group(1)
                        if not photo_path.startswith('http'):
                            photo_url = f"https://www.sherdog.com{photo_path}"
                        else:
                            photo_url = photo_path
                        logger.debug(f"Found Sherdog og:image for {name}: {photo_url}")
                        return photo_url

                    # Способ 2: itemprop="image" img tag
                    img_match = re.search(r'itemprop="image"\s+src="([^"]+)"', fighter_html)
                    if img_match:
                        photo_path = img_match.group(1)
                        if not photo_path.startswith('http'):
                            photo_url = f"https://www.sherdog.com{photo_path}"
                        else:
                            photo_url = photo_path
                        logger.debug(f"Found Sherdog itemprop image for {name}: {photo_url}")
                        return photo_url

                    logger.debug(f"No photo on Sherdog for {name}")
                    return ""

        except Exception as e:
            logger.debug(f"Error getting Sherdog photo for {name}: {e}")
            return ""


async def get_fighter_info(name: str) -> Optional[Fighter]:
    """Удобная функция для получения данных бойца."""
    async with FighterScraper() as scraper:
        return await scraper.get_fighter(name)


async def get_fighters_for_event(fighter_names: list[str]) -> dict[str, Fighter]:
    """Получает данные для списка бойцов."""
    result = {}
    async with FighterScraper() as scraper:
        for name in fighter_names:
            fighter = await scraper.get_fighter(name)
            if fighter:
                result[name.lower()] = fighter
    return result
