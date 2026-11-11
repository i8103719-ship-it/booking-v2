import asyncio
import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType # <--- ИСПРАВЛЕНО ЗДЕСЬ

# ==========================================
# НАСТРОЙКИ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
SHEET_URL = os.getenv("SHEET_URL")

# ==========================================
# ЛОГИРОВАНИЕ
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ==========================================
# GOOGLE SHEETS
# ==========================================

def get_google_sheet():
    """
    Подключение к Google Sheets через сервисный аккаунт.
    """
    credentials_dict = json.loads(GOOGLE_CREDS)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        credentials_dict,
        scopes=scopes
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_url(SHEET_URL)

    return spreadsheet.sheet1


def save_to_google_sheets(date, time, service, price, username):
    """
    Сохранение записи в Google Таблицу.
    """
    try:
        worksheet = get_google_sheet()

        row = [
            date,
            time,
            service,
            price,
            username
        ]

        worksheet.append_row(
            row,
            value_input_option="USER_ENTERED"
        )

        logger.info("Запись успешно сохранена в Google Sheets")
        return True

    except Exception:
        logger.exception("Ошибка при записи в Google Sheets")
        return False

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ==========================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()

# ==========================================
# КОМАНДА START
# ==========================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✨ Записаться онлайн",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "<b>ATELIER BEAUTY</b>\n\n"
        "Добро пожаловать!\n"
        "Вы можете выбрать услугу и удобное время "
        "для записи через наше приложение.",
        reply_markup=keyboard
    )

# ==========================================
# ОБРАБОТКА ДАННЫХ MINI APP
# ==========================================

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_handler(message: Message):
    try:
        # Получаем JSON от Mini App
        raw_data = message.web_app_data.data
        data = json.loads(raw_data)

        # Извлекаем данные записи
        service = str(data["service"])
        price = int(data["price"])
        time = str(data["time"])
        date = str(data["date"])

        # Получаем username клиента
        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "Не указан"
        )

        # Проверяем обязательные поля
        if not service or not date or not time:
            raise ValueError("Не заполнены обязательные поля")

        if price < 0:
            raise ValueError("Некорректная цена")

        # Сохраняем запись в Google Sheets (в отдельном потоке, чтобы не вешать бота)
        saved = await asyncio.to_thread(
            save_to_google_sheets,
            date,
            time,
            service,
            price,
            username
        )

        # Уведомление администратора
        admin_text = (
            "<b>💅 НОВАЯ ЗАПИСЬ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Услуга:</b> {service}\n"
            f"<b>Дата:</b> {date}\n"
            f"<b>Время:</b> {time}\n"
            f"<b>Цена:</b> {price:,} ₽\n"
            f"<b>Клиент:</b> {username}\n"
            f"<b>Telegram ID:</b> {message.from_user.id}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Google Sheets:</b> "
            f"{'✅ Записано' if saved else '❌ Ошибка сохранения'}"
        )

        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text
            )
        except Exception:
            logger.exception("Не удалось отправить уведомление администратору")

        # Подтверждение пользователю
        await message.answer(
            f"✅ Спасибо! Вы записаны на <b>{service}</b>\n\n"
            f"<b>Дата:</b> {date}\n"
            f"<b>Время:</b> {time}\n"
            f"<b>Стоимость:</b> {price:,} ₽\n\n"
            "Администратор свяжется с вами для подтверждения."
        )

    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.exception("Некорректные данные от Mini App")
        await message.answer(
            "Не удалось обработать вашу заявку. "
            "Пожалуйста, попробуйте записаться ещё раз."
        )

    except Exception:
        logger.exception("Неожиданная ошибка обработки записи")
        await message.answer(
            "Произошла ошибка при обработке записи. "
            "Попробуйте позже."
        )

# ==========================================
# ЗАПУСК БОТА
# ==========================================

async def main():
    if not BOT_TOKEN:
        raise ValueError("Не задан BOT_TOKEN")
    if not ADMIN_ID:
        raise ValueError("Не задан ADMIN_ID")
    if not WEBAPP_URL:
        raise ValueError("Не задан WEBAPP_URL")

    logger.info("Бот-запись v2 запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
