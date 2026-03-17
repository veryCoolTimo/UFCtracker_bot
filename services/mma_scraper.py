import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import hashlib

from models.event import Event, Fight
from config import MMA_LEAGUES

logger = logging.getLogger(__name__)

# ESPN API endpoints
ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports/mma"
ESPN_API_URLS = {
    "UFC": f"{ESPN_API_BASE}/ufc/scoreboard",
    "Bellator": f"{ESPN_API_BASE}/bellator/scoreboard",
    "PFL": f"{ESPN_API_BASE}/pfl/scoreboard",
}


class MMAScraper:
    """Парсер событий MMA через ESPN API."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.HEADERS)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _generate_event_id(self, espn_id: str, league: str) -> str:
        """Генерирует уникальный ID для события."""
        return f"{league.lower()}_{espn_id}"

    def _parse_date(self, date_str: str) -> datetime:
        """Парсит ISO дату."""
        try:
            # Формат: 2026-03-21T17:00Z
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            return datetime.now(timezone.utc)

    def _parse_fight_from_name(self, event_name: str) -> Optional[Fight]:
        """Парсит main event из названия события."""
        import re
        # Паттерн: "UFC Fight Night: Evloev vs. Murphy"
        match = re.search(r":\s*([A-Za-z\'\-\.\s]+?)\s+vs\.?\s+([A-Za-z\'\-\.\s]+?)$", event_name, re.IGNORECASE)
        if match:
            return Fight(fighter1=match.group(1).strip(), fighter2=match.group(2).strip())
        return None

    async def fetch_league_events(self, league_key: str) -> list[Event]:
        """Получает события для одной лиги через ESPN API."""
        if not self.session:
            raise RuntimeError("Scraper должен использоваться как context manager")

        api_url = ESPN_API_URLS.get(league_key)
        if not api_url:
            logger.warning(f"Нет API URL для лиги: {league_key}")
            return []

        events = []

        try:
            async with self.session.get(api_url) as response:
                if response.status != 200:
                    logger.error(f"ESPN API вернул статус {response.status} для {league_key}")
                    return events

                data = await response.json()

                for event_data in data.get("events", []):
                    event = self._parse_event(event_data, league_key)
                    if event:
                        events.append(event)

        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при запросе {league_key}: {e}")
        except Exception as e:
            logger.error(f"Ошибка парсинга {league_key}: {e}")

        logger.info(f"Найдено {len(events)} событий {league_key}")
        return events

    def _parse_event(self, data: dict, league: str) -> Optional[Event]:
        """Парсит событие из JSON данных ESPN API."""
        try:
            espn_id = data.get("id", "")
            name = data.get("name", "")
            date_str = data.get("date", "")

            if not name or not date_str:
                return None

            event_date = self._parse_date(date_str)

            # Получаем локацию из первого competition
            location = ""
            venue = ""
            competitions = data.get("competitions", [])

            # Ищем main event (обычно первый бой в списке с самым высоким billing)
            main_event = None
            main_event_fights = []

            for comp in competitions:
                # Venue
                venue_data = comp.get("venue", {})
                if venue_data and not venue:
                    venue = venue_data.get("fullName", "")
                    addr = venue_data.get("address", {})
                    city = addr.get("city", "")
                    country = addr.get("country", "")
                    if city:
                        location = f"{city}, {country}" if country else city

                # Competitors (fighters)
                competitors = comp.get("competitors", [])
                if len(competitors) >= 2:
                    fighter1_data = competitors[0].get("athlete", {})
                    fighter2_data = competitors[1].get("athlete", {})

                    f1_name = fighter1_data.get("displayName", "")
                    f2_name = fighter2_data.get("displayName", "")

                    # Records
                    f1_record = ""
                    f2_record = ""

                    for rec in competitors[0].get("records", []):
                        if rec.get("type") == "total":
                            f1_record = rec.get("summary", "")
                            break

                    for rec in competitors[1].get("records", []):
                        if rec.get("type") == "total":
                            f2_record = rec.get("summary", "")
                            break

                    if f1_name and f2_name:
                        fight = Fight(
                            fighter1=f1_name,
                            fighter2=f2_name,
                            weight_class=comp.get("type", {}).get("abbreviation", "")
                        )
                        main_event_fights.append(fight)

            # Парсим main event из названия события (более надёжно)
            main_event = self._parse_fight_from_name(name)

            # Если не удалось - берём последний бой (main event обычно в конце)
            if not main_event and main_event_fights:
                main_event = main_event_fights[-1]

            # URL события
            url = f"https://www.espn.com/mma/fightcenter/_/id/{espn_id}/league/{league.lower()}"

            return Event(
                id=self._generate_event_id(espn_id, league),
                name=name,
                date=event_date,
                league=league,
                location=location,
                venue=venue,
                url=url,
                main_event=main_event,
                fights=main_event_fights[:5]  # Первые 5 боёв
            )

        except Exception as e:
            logger.error(f"Ошибка парсинга события: {e}")
            return None

    async def fetch_all_events(self) -> list[Event]:
        """Получает события со всех лиг параллельно."""
        tasks = [
            self.fetch_league_events(league_key)
            for league_key in ESPN_API_URLS.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_events = []
        for result in results:
            if isinstance(result, list):
                all_events.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Ошибка при получении событий: {result}")

        return all_events


async def get_upcoming_events(leagues: list[str] = None, fetch_details: bool = False) -> list[Event]:
    """
    Получает предстоящие события MMA.

    Args:
        leagues: Список лиг для получения (по умолчанию все)
        fetch_details: Не используется (данные уже полные из API)
    """
    async with MMAScraper() as scraper:
        if leagues:
            # Фильтруем только поддерживаемые лиги
            valid_leagues = [l for l in leagues if l in ESPN_API_URLS]
            tasks = [scraper.fetch_league_events(league) for league in valid_leagues]
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

        return upcoming
