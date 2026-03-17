import aiohttp
import logging
import io
import os
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from dataclasses import dataclass

from services.fighter_scraper import Fighter, get_fighter_info
from config import DATA_DIR

logger = logging.getLogger(__name__)

# Папка для шрифтов и ассетов
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

# Цвета
COLORS = {
    "bg_dark": (20, 20, 25),
    "bg_card": (30, 30, 35),
    "accent": (200, 55, 55),  # UFC красный
    "gold": (212, 175, 55),    # Золотой для чемпионов
    "white": (255, 255, 255),
    "gray": (150, 150, 150),
    "light_gray": (200, 200, 200),
    "vs_red": (220, 50, 50),
}


@dataclass
class FightCardData:
    """Данные для генерации карточки боя."""
    event_name: str
    event_date: str
    fighter1_name: str
    fighter2_name: str
    fighter1_record: str = ""
    fighter2_record: str = ""
    fighter1_photo: Optional[bytes] = None
    fighter2_photo: Optional[bytes] = None
    fighter1_rank: str = ""
    fighter2_rank: str = ""
    weight_class: str = ""
    is_title_fight: bool = False


class FightCardGenerator:
    """Генератор изображений карточек боёв."""

    CARD_WIDTH = 800
    CARD_HEIGHT = 500
    PHOTO_SIZE = 180

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._font_cache = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Получает шрифт нужного размера."""
        key = (size, bold)
        if key not in self._font_cache:
            try:
                # Пробуем системные шрифты
                font_names = [
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]

                for font_path in font_names:
                    if os.path.exists(font_path):
                        self._font_cache[key] = ImageFont.truetype(font_path, size)
                        return self._font_cache[key]

                # Fallback
                self._font_cache[key] = ImageFont.load_default()
            except Exception:
                self._font_cache[key] = ImageFont.load_default()

        return self._font_cache[key]

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Скачивает изображение по URL."""
        if not self.session or not url:
            return None

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            logger.debug(f"Could not download image from {url}: {e}")

        return None

    def _create_circular_image(self, img_bytes: bytes, size: int) -> Image.Image:
        """Создаёт круглое изображение."""
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img = img.convert("RGBA")

            # Ресайз
            img = img.resize((size, size), Image.Resampling.LANCZOS)

            # Создаём маску
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            # Применяем маску
            output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            output.paste(img, (0, 0))
            output.putalpha(mask)

            return output
        except Exception as e:
            logger.error(f"Error creating circular image: {e}")
            return self._create_placeholder(size)

    def _create_placeholder(self, size: int) -> Image.Image:
        """Создаёт placeholder для отсутствующего фото."""
        img = Image.new("RGBA", (size, size), COLORS["bg_card"])
        draw = ImageDraw.Draw(img)

        # Круг
        draw.ellipse((0, 0, size - 1, size - 1), fill=COLORS["bg_dark"], outline=COLORS["gray"], width=2)

        # Иконка человека
        center = size // 2
        head_r = size // 6
        draw.ellipse(
            (center - head_r, center - head_r - size // 8, center + head_r, center + head_r - size // 8),
            fill=COLORS["gray"]
        )
        draw.ellipse(
            (center - size // 4, center + size // 10, center + size // 4, center + size // 2),
            fill=COLORS["gray"]
        )

        return img

    async def generate_fight_card(self, data: FightCardData) -> bytes:
        """Генерирует изображение карточки боя."""

        # Создаём основу
        img = Image.new("RGB", (self.CARD_WIDTH, self.CARD_HEIGHT), COLORS["bg_dark"])
        draw = ImageDraw.Draw(img)

        # Шрифты
        font_title = self._get_font(28, bold=True)
        font_name = self._get_font(24, bold=True)
        font_record = self._get_font(20)
        font_info = self._get_font(16)
        font_vs = self._get_font(36, bold=True)
        font_small = self._get_font(14)

        # === Заголовок ===
        title_y = 25

        # Название события
        title_text = data.event_name
        bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = bbox[2] - bbox[0]
        draw.text(
            ((self.CARD_WIDTH - title_width) // 2, title_y),
            title_text,
            fill=COLORS["white"],
            font=font_title
        )

        # Дата
        date_y = title_y + 35
        bbox = draw.textbbox((0, 0), data.event_date, font=font_info)
        date_width = bbox[2] - bbox[0]
        draw.text(
            ((self.CARD_WIDTH - date_width) // 2, date_y),
            data.event_date,
            fill=COLORS["gray"],
            font=font_info
        )

        # Title fight badge
        if data.is_title_fight:
            badge_y = date_y + 25
            badge_text = "🏆 TITLE FIGHT"
            bbox = draw.textbbox((0, 0), badge_text, font=font_small)
            badge_width = bbox[2] - bbox[0]
            draw.text(
                ((self.CARD_WIDTH - badge_width) // 2, badge_y),
                badge_text,
                fill=COLORS["gold"],
                font=font_small
            )

        # === Фотографии бойцов ===
        photo_y = 120
        fighter1_x = 120
        fighter2_x = self.CARD_WIDTH - 120 - self.PHOTO_SIZE

        # Fighter 1 photo
        if data.fighter1_photo:
            photo1 = self._create_circular_image(data.fighter1_photo, self.PHOTO_SIZE)
        else:
            photo1 = self._create_placeholder(self.PHOTO_SIZE)
        img.paste(photo1, (fighter1_x, photo_y), photo1)

        # Fighter 2 photo
        if data.fighter2_photo:
            photo2 = self._create_circular_image(data.fighter2_photo, self.PHOTO_SIZE)
        else:
            photo2 = self._create_placeholder(self.PHOTO_SIZE)
        img.paste(photo2, (fighter2_x, photo_y), photo2)

        # === VS ===
        vs_text = "VS"
        bbox = draw.textbbox((0, 0), vs_text, font=font_vs)
        vs_width = bbox[2] - bbox[0]
        vs_x = (self.CARD_WIDTH - vs_width) // 2
        vs_y = photo_y + self.PHOTO_SIZE // 2 - 20
        draw.text((vs_x, vs_y), vs_text, fill=COLORS["vs_red"], font=font_vs)

        # === Имена бойцов ===
        name_y = photo_y + self.PHOTO_SIZE + 15

        # Fighter 1 name
        name1 = data.fighter1_name.upper()
        bbox = draw.textbbox((0, 0), name1, font=font_name)
        name1_width = bbox[2] - bbox[0]
        name1_x = fighter1_x + (self.PHOTO_SIZE - name1_width) // 2
        draw.text((name1_x, name_y), name1, fill=COLORS["white"], font=font_name)

        # Fighter 2 name
        name2 = data.fighter2_name.upper()
        bbox = draw.textbbox((0, 0), name2, font=font_name)
        name2_width = bbox[2] - bbox[0]
        name2_x = fighter2_x + (self.PHOTO_SIZE - name2_width) // 2
        draw.text((name2_x, name_y), name2, fill=COLORS["white"], font=font_name)

        # === Рекорды ===
        record_y = name_y + 30

        # Fighter 1 record
        if data.fighter1_record:
            record1 = data.fighter1_record
            bbox = draw.textbbox((0, 0), record1, font=font_record)
            record1_width = bbox[2] - bbox[0]
            record1_x = fighter1_x + (self.PHOTO_SIZE - record1_width) // 2
            draw.text((record1_x, record_y), record1, fill=COLORS["light_gray"], font=font_record)

        # Fighter 2 record
        if data.fighter2_record:
            record2 = data.fighter2_record
            bbox = draw.textbbox((0, 0), record2, font=font_record)
            record2_width = bbox[2] - bbox[0]
            record2_x = fighter2_x + (self.PHOTO_SIZE - record2_width) // 2
            draw.text((record2_x, record_y), record2, fill=COLORS["light_gray"], font=font_record)

        # === Ranks ===
        if data.fighter1_rank or data.fighter2_rank:
            rank_y = record_y + 25

            if data.fighter1_rank:
                rank1 = data.fighter1_rank
                bbox = draw.textbbox((0, 0), rank1, font=font_small)
                rank1_width = bbox[2] - bbox[0]
                rank1_x = fighter1_x + (self.PHOTO_SIZE - rank1_width) // 2
                draw.text((rank1_x, rank_y), rank1, fill=COLORS["gold"], font=font_small)

            if data.fighter2_rank:
                rank2 = data.fighter2_rank
                bbox = draw.textbbox((0, 0), rank2, font=font_small)
                rank2_width = bbox[2] - bbox[0]
                rank2_x = fighter2_x + (self.PHOTO_SIZE - rank2_width) // 2
                draw.text((rank2_x, rank_y), rank2, fill=COLORS["gold"], font=font_small)

        # === Weight class ===
        if data.weight_class:
            wc_y = self.CARD_HEIGHT - 50
            bbox = draw.textbbox((0, 0), data.weight_class, font=font_info)
            wc_width = bbox[2] - bbox[0]
            draw.text(
                ((self.CARD_WIDTH - wc_width) // 2, wc_y),
                data.weight_class,
                fill=COLORS["gray"],
                font=font_info
            )

        # === Декоративные линии ===
        line_y = 95
        draw.line([(50, line_y), (self.CARD_WIDTH - 50, line_y)], fill=COLORS["accent"], width=2)

        bottom_line_y = self.CARD_HEIGHT - 25
        draw.line([(50, bottom_line_y), (self.CARD_WIDTH - 50, bottom_line_y)], fill=COLORS["accent"], width=2)

        # === Сохраняем в bytes ===
        output = io.BytesIO()
        img.save(output, format="PNG", quality=95)
        output.seek(0)

        return output.getvalue()


async def generate_main_event_card(
    event_name: str,
    event_date: str,
    fighter1_name: str,
    fighter2_name: str,
    weight_class: str = "",
    is_title_fight: bool = False
) -> bytes:
    """Генерирует карточку main event."""

    async with FightCardGenerator() as generator:
        # Получаем данные бойцов
        fighter1 = await get_fighter_info(fighter1_name)
        fighter2 = await get_fighter_info(fighter2_name)

        # Скачиваем фото
        photo1 = None
        photo2 = None

        if fighter1 and fighter1.photo_url:
            photo1 = await generator._download_image(fighter1.photo_url)
        if fighter2 and fighter2.photo_url:
            photo2 = await generator._download_image(fighter2.photo_url)

        # Формируем данные
        data = FightCardData(
            event_name=event_name,
            event_date=event_date,
            fighter1_name=fighter1_name,
            fighter2_name=fighter2_name,
            fighter1_record=fighter1.record if fighter1 else "",
            fighter2_record=fighter2.record if fighter2 else "",
            fighter1_photo=photo1,
            fighter2_photo=photo2,
            fighter1_rank=fighter1.rank if fighter1 else "",
            fighter2_rank=fighter2.rank if fighter2 else "",
            weight_class=weight_class,
            is_title_fight=is_title_fight
        )

        return await generator.generate_fight_card(data)
