import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Optional
import re
import hashlib

from models.event import Event, Fight
from config import MMA_LEAGUES

logger = logging.getLogger(__name__)


class MMAScraper:
    """Парсер событий MMA с ESPN для всех лиг."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.HEADERS)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _generate_event_id(self, name: str, date: datetime, league: str) -> str:
        """Генерирует уникальный ID для события."""
        unique_string = f"{league}_{name}_{date.isoformat()}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Парсит строку даты в datetime."""
        try:
            formats = [
                "%a, %b %d",  # Sat, Apr 12
                "%B %d, %Y",  # April 12, 2026
                "%b %d, %Y",  # Apr 12, 2026
                "%b %d",      # Apr 12
                "%Y-%m-%dT%H:%M:%SZ",  # ISO format
                "%Y-%m-%dT%H:%M:%S",
            ]

            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_str.strip(), fmt)
                    if parsed.year == 1900:
                        now = datetime.now()
                        parsed = parsed.replace(year=now.year)
                        if parsed < now:
                            parsed = parsed.replace(year=now.year + 1)
                    return parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

            logger.debug(f"Не удалось распарсить дату: {date_str}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга даты {date_str}: {e}")
            return None

    async def fetch_league_events(self, league_key: str) -> list[Event]:
        """Получает события для одной лиги."""
        if not self.session:
            raise RuntimeError("Scraper должен использоваться как context manager")

        league_info = MMA_LEAGUES.get(league_key)
        if not league_info:
            logger.error(f"Неизвестная лига: {league_key}")
            return []

        url = league_info["url"]
        league_name = league_info["name"]
        events = []

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"ESPN вернул статус {response.status} для {league_key}")
                    return events

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                # Ищем таблицы расписания
                schedule_tables = soup.find_all("div", class_="ResponsiveTable")
                if not schedule_tables:
                    schedule_tables = soup.find_all("table", class_="Table")

                for table in schedule_tables:
                    rows = table.find_all("tr")
                    current_date = None

                    for row in rows:
                        date_header = row.find("td", class_="Table__Title")
                        if date_header:
                            current_date = self._parse_date(date_header.get_text(strip=True))
                            continue

                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            event = self._parse_event_row(cells, current_date, league_key)
                            if event:
                                events.append(event)

                # Альтернативный парсинг
                if not events:
                    events = self._parse_event_cards(soup, league_key)

        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при запросе {league_key}: {e}")
        except Exception as e:
            logger.error(f"Ошибка парсинга {league_key}: {e}")

        logger.info(f"Найдено {len(events)} событий {league_name}")
        return events

    def _parse_event_row(self, cells, current_date: Optional[datetime], league: str) -> Optional[Event]:
        """Парсит строку таблицы в событие."""
        try:
            name_cell = cells[0]
            name_link = name_cell.find("a")

            if name_link:
                name = name_link.get_text(strip=True)
                url = name_link.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://www.espn.com{url}"
            else:
                name = name_cell.get_text(strip=True)
                url = ""

            if not name:
                return None

            # Ищем дату
            event_date = current_date
            for cell in cells:
                text = cell.get_text(strip=True)
                parsed_date = self._parse_date(text)
                if parsed_date:
                    event_date = parsed_date
                    break

            if not event_date:
                event_date = datetime.now(timezone.utc)

            # Ищем локацию
            location = ""
            for cell in cells[1:]:
                text = cell.get_text(strip=True)
                if "," in text and not self._parse_date(text):
                    location = text
                    break

            event_id = self._generate_event_id(name, event_date, league)

            return Event(
                id=event_id,
                name=name,
                date=event_date,
                league=league,
                location=location,
                url=url
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга строки события: {e}")
            return None

    def _parse_event_cards(self, soup: BeautifulSoup, league: str) -> list[Event]:
        """Альтернативный парсинг через карточки событий."""
        events = []
        cards = soup.find_all("article") or soup.find_all("div", class_=re.compile(r"event|card", re.I))

        for card in cards:
            try:
                title = card.find(["h1", "h2", "h3", "a"])
                if not title:
                    continue

                name = title.get_text(strip=True)
                if not name:
                    continue

                link = card.find("a")
                url = ""
                if link and link.get("href"):
                    url = link["href"]
                    if not url.startswith("http"):
                        url = f"https://www.espn.com{url}"

                date_elem = card.find(class_=re.compile(r"date|time", re.I))
                event_date = datetime.now(timezone.utc)
                if date_elem:
                    parsed = self._parse_date(date_elem.get_text(strip=True))
                    if parsed:
                        event_date = parsed

                location = ""
                location_elem = card.find(class_=re.compile(r"location|venue", re.I))
                if location_elem:
                    location = location_elem.get_text(strip=True)

                event_id = self._generate_event_id(name, event_date, league)

                events.append(Event(
                    id=event_id,
                    name=name,
                    date=event_date,
                    league=league,
                    location=location,
                    url=url
                ))
            except Exception as e:
                logger.debug(f"Ошибка парсинга карточки: {e}")
                continue

        return events

    async def fetch_event_details(self, event: Event) -> Event:
        """Получает детали события (main event, fight card)."""
        if not self.session or not event.url:
            return event

        try:
            async with self.session.get(event.url) as response:
                if response.status != 200:
                    return event

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                # Пробуем найти main event разными способами

                # Способ 1: Ищем заголовок с именами бойцов
                headline = soup.find("h1", class_=re.compile(r"headline", re.I))
                if headline:
                    text = headline.get_text(strip=True)
                    fight = self._parse_fight_from_text(text)
                    if fight:
                        event.main_event = fight

                # Способ 2: Ищем секцию с боями
                if not event.main_event:
                    fight_sections = soup.find_all(class_=re.compile(r"fight|matchup|bout", re.I))
                    for section in fight_sections:
                        fighters = section.find_all(class_=re.compile(r"fighter|name|competitor", re.I))
                        if len(fighters) >= 2:
                            f1 = fighters[0].get_text(strip=True)
                            f2 = fighters[1].get_text(strip=True)
                            if f1 and f2:
                                event.main_event = Fight(fighter1=f1, fighter2=f2)
                                break

                # Способ 3: Ищем в названии события
                if not event.main_event:
                    fight = self._parse_fight_from_text(event.name)
                    if fight:
                        event.main_event = fight

                # Способ 4: Ищем ссылки на бойцов
                if not event.main_event:
                    fighter_links = soup.find_all("a", href=re.compile(r"/mma/fighter/", re.I))
                    if len(fighter_links) >= 2:
                        f1 = fighter_links[0].get_text(strip=True)
                        f2 = fighter_links[1].get_text(strip=True)
                        if f1 and f2 and f1 != f2:
                            event.main_event = Fight(fighter1=f1, fighter2=f2)

                # Ищем venue/location
                venue_elem = soup.find(class_=re.compile(r"venue|location|arena", re.I))
                if venue_elem and not event.venue:
                    event.venue = venue_elem.get_text(strip=True)

        except Exception as e:
            logger.debug(f"Ошибка получения деталей события {event.name}: {e}")

        return event

    def _parse_fight_from_text(self, text: str) -> Optional[Fight]:
        """Парсит имена бойцов из текста."""
        # Паттерны: "Fighter1 vs Fighter2", "Fighter1 vs. Fighter2", "Fighter1 v Fighter2"
        patterns = [
            r"([A-Za-z\'\-\.\s]+?)\s+vs\.?\s+([A-Za-z\'\-\.\s]+)",
            r"([A-Za-z\'\-\.\s]+?)\s+v\s+([A-Za-z\'\-\.\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                f1 = match.group(1).strip()
                f2 = match.group(2).strip()

                # Убираем лишние слова
                for word in ["UFC", "PFL", "Bellator", "Fight Night", "Main Event", ":", "-"]:
                    f1 = f1.replace(word, "").strip()
                    f2 = f2.replace(word, "").strip()

                if f1 and f2 and len(f1) > 2 and len(f2) > 2:
                    # Определяем title fight
                    is_title = "title" in text.lower() or "championship" in text.lower()

                    # Ищем весовую категорию
                    weight_class = ""
                    weight_patterns = [
                        r"(Lightweight|Welterweight|Middleweight|Heavyweight|Featherweight|Bantamweight|Flyweight|Light Heavyweight|Strawweight|Women's)",
                    ]
                    for wp in weight_patterns:
                        wm = re.search(wp, text, re.IGNORECASE)
                        if wm:
                            weight_class = wm.group(1)
                            break

                    return Fight(
                        fighter1=f1,
                        fighter2=f2,
                        weight_class=weight_class,
                        is_title_fight=is_title
                    )

        return None

    async def fetch_all_events(self) -> list[Event]:
        """Получает события со всех лиг параллельно."""
        tasks = [
            self.fetch_league_events(league_key)
            for league_key in MMA_LEAGUES.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_events = []
        for result in results:
            if isinstance(result, list):
                all_events.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Ошибка при получении событий: {result}")

        return all_events


async def get_upcoming_events(leagues: list[str] = None, fetch_details: bool = True) -> list[Event]:
    """
    Получает предстоящие события MMA.

    Args:
        leagues: Список лиг для получения (по умолчанию все)
        fetch_details: Загружать ли детали событий (main event)
    """
    async with MMAScraper() as scraper:
        if leagues:
            tasks = [scraper.fetch_league_events(league) for league in leagues]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            events = []
            for result in results:
                if isinstance(result, list):
                    events.extend(result)
        else:
            events = await scraper.fetch_all_events()

        # Фильтруем только будущие события
        now = datetime.now(timezone.utc)
        upcoming = [e for e in events if e.date > now]

        # Сортируем по дате
        upcoming.sort(key=lambda e: e.date)

        # Загружаем детали для первых N событий
        if fetch_details and upcoming:
            # Загружаем детали для первых 5 событий параллельно
            events_to_fetch = upcoming[:5]
            detail_tasks = [scraper.fetch_event_details(e) for e in events_to_fetch]
            detailed_events = await asyncio.gather(*detail_tasks, return_exceptions=True)

            # Заменяем события с деталями
            for i, result in enumerate(detailed_events):
                if isinstance(result, Event):
                    upcoming[i] = result

        return upcoming
