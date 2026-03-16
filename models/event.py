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

    def format_message(self, timezone_str: str = "Europe/Moscow") -> str:
        """Форматирует событие для отправки в Telegram."""
        from zoneinfo import ZoneInfo
        from config import MMA_LEAGUES

        tz = ZoneInfo(timezone_str)
        local_date = self.date.astimezone(tz)

        # Форматирование даты на русском
        months = [
            "", "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        date_str = f"{local_date.day} {months[local_date.month]} {local_date.year}"
        time_str = local_date.strftime("%H:%M")

        # Получаем emoji для лиги
        league_info = MMA_LEAGUES.get(self.league, {})
        emoji = league_info.get("emoji", "🥊")

        lines = [
            f"{emoji} <b>{self.name}</b>",
            "",
            f"📅 {date_str}, {time_str} (МСК)",
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
                "🎯 <b>Главный бой:</b>",
                f"{self.main_event.fighter1} vs {self.main_event.fighter2}"
            ])
            if self.main_event.weight_class:
                title_text = " (Title)" if self.main_event.is_title_fight else ""
                lines.append(f"({self.main_event.weight_class}{title_text})")

        if self.url:
            lines.extend([
                "",
                f"🔗 <a href=\"{self.url}\">Подробнее</a>"
            ])

        return "\n".join(lines)

    def hours_until(self) -> float:
        """Возвращает количество часов до события."""
        now = datetime.now(self.date.tzinfo)
        delta = self.date - now
        return delta.total_seconds() / 3600
