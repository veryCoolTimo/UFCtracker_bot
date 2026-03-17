from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class Fight:
    fighter1: str
    fighter2: str
    weight_class: str = ""
    is_title_fight: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Fight":
        return cls(**data)

    def __str__(self) -> str:
        title = " (Title)" if self.is_title_fight else ""
        weight = f" - {self.weight_class}" if self.weight_class else ""
        return f"{self.fighter1} vs {self.fighter2}{weight}{title}"


@dataclass
class Event:
    id: str
    name: str
    date: datetime
    league: str = "UFC"
    location: str = ""
    venue: str = ""
    main_event: Optional[Fight] = None
    url: str = ""
    fights: list[Fight] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "date": self.date.isoformat(),
            "league": self.league,
            "location": self.location,
            "venue": self.venue,
            "url": self.url,
            "main_event": self.main_event.to_dict() if self.main_event else None,
            "fights": [f.to_dict() for f in self.fights]
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        main_event = None
        if data.get("main_event"):
            main_event = Fight.from_dict(data["main_event"])

        fights = [Fight.from_dict(f) for f in data.get("fights", [])]

        return cls(
            id=data["id"],
            name=data["name"],
            date=datetime.fromisoformat(data["date"]),
            league=data.get("league", "UFC"),
            location=data.get("location", ""),
            venue=data.get("venue", ""),
            url=data.get("url", ""),
            main_event=main_event,
            fights=fights
        )

    def format_message(self, region: str = "US") -> str:
        """Форматирует событие для отправки в Telegram."""
        from zoneinfo import ZoneInfo
        from config import MMA_LEAGUES, STREAMING_BY_REGION, TIMEZONE_BY_REGION

        # Таймзона по региону
        tz_str = TIMEZONE_BY_REGION.get(region, "America/New_York")
        tz = ZoneInfo(tz_str)
        local_date = self.date.astimezone(tz)

        # Название таймзоны
        tz_names = {"America/New_York": "ET", "Europe/Berlin": "CET", "Europe/Moscow": "MSK"}
        tz_name = tz_names.get(tz_str, tz_str)

        # Форматирование даты
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{local_date.day} {months[local_date.month]} {local_date.year}"
        time_str = local_date.strftime("%H:%M")

        # Инфо о лиге
        league_info = MMA_LEAGUES.get(self.league, {})
        emoji = league_info.get("emoji", "🥊")
        official_url = league_info.get("official_url", "")

        # Стриминг по региону
        region_streaming = STREAMING_BY_REGION.get(region, {})
        watch_list = region_streaming.get(self.league, [])

        lines = [
            f"{emoji} <b>{self.name}</b>",
            "",
            f"📅 {date_str}, {time_str} ({tz_name})",
        ]

        if self.venue or self.location:
            location_parts = []
            if self.venue:
                location_parts.append(self.venue)
            if self.location:
                location_parts.append(self.location)
            lines.append(f"📍 {', '.join(location_parts)}")

        if self.main_event:
            lines.extend([
                "",
                "🎯 <b>Main Event:</b>",
                f"{self.main_event.fighter1} vs {self.main_event.fighter2}"
            ])
            if self.main_event.weight_class:
                title_text = " (Title)" if self.main_event.is_title_fight else ""
                lines.append(f"({self.main_event.weight_class}{title_text})")

        # Где смотреть
        if watch_list:
            lines.extend([
                "",
                "📺 <b>Watch:</b>",
                " | ".join(watch_list)
            ])

        # Ссылки
        links = []
        if self.url:
            links.append(f"<a href=\"{self.url}\">ESPN</a>")
        if official_url:
            links.append(f"<a href=\"{official_url}\">Official</a>")

        if links:
            lines.extend([
                "",
                f"🔗 {' • '.join(links)}"
            ])

        return "\n".join(lines)

    def hours_until(self) -> float:
        """Возвращает количество часов до события."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        if self.date.tzinfo is None:
            event_date = self.date.replace(tzinfo=timezone.utc)
        else:
            event_date = self.date
        delta = event_date - now
        return delta.total_seconds() / 3600

    def format_countdown(self) -> str:
        """Форматирует countdown до события."""
        hours = self.hours_until()

        if hours <= 0:
            return "🔴 Event is LIVE or finished!"

        days = int(hours // 24)
        remaining_hours = int(hours % 24)
        minutes = int((hours % 1) * 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if remaining_hours > 0:
            parts.append(f"{remaining_hours}h")
        if minutes > 0 and days == 0:  # показываем минуты только если меньше дня
            parts.append(f"{minutes}m")

        return f"⏱ {' '.join(parts)}"

    def generate_ics(self) -> str:
        """Генерирует ICS файл для события."""
        from datetime import timedelta

        # ICS формат
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//MMA Bot//mmabot//EN",
            "BEGIN:VEVENT",
            f"UID:{self.id}@mmabot",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{self.date.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{(self.date + timedelta(hours=4)).strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{self.name}",
        ]

        if self.location:
            lines.append(f"LOCATION:{self.location}")

        description = f"League: {self.league}"
        if self.main_event:
            description += f"\\nMain Event: {self.main_event.fighter1} vs {self.main_event.fighter2}"
        if self.url:
            description += f"\\nMore info: {self.url}"

        lines.append(f"DESCRIPTION:{description}")
        lines.append("END:VEVENT")
        lines.append("END:VCALENDAR")

        return "\r\n".join(lines)
