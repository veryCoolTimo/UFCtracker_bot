import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from bot.handlers import router
from services.scheduler import EventScheduler
from storage.json_storage import NotificationStorage, SubscriberStorage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота."""

    # Проверяем токен
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен! Создайте файл .env на основе .env.example")
        sys.exit(1)

    # Инициализируем бота
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Инициализируем диспетчер
    dp = Dispatcher()
    dp.include_router(router)

    # Инициализируем хранилища
    notification_storage = NotificationStorage()
    subscriber_storage = SubscriberStorage()

    # Автоматически добавляем админа в подписчики
    if ADMIN_CHAT_ID:
        try:
            admin_id = int(ADMIN_CHAT_ID)
            subscriber_storage.add_subscriber(admin_id)
            logger.info(f"Админ {admin_id} добавлен в подписчики")
        except ValueError:
            logger.warning(f"Некорректный ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")

    # Функция для отправки сообщений из планировщика
    async def send_message(chat_id: int, text: str):
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    # Инициализируем планировщик
    scheduler = EventScheduler(
        send_message=send_message,
        notification_storage=notification_storage,
        subscriber_storage=subscriber_storage
    )

    logger.info("Запуск UFC Bot...")

    try:
        # Запускаем планировщик
        await scheduler.start()

        # Уведомляем админа о запуске
        if ADMIN_CHAT_ID:
            try:
                await bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text="🤖 Бот запущен и готов к работе!"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление админу: {e}")

        # Запускаем бота
        await dp.start_polling(bot)

    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
