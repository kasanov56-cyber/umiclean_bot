import os
import logging
import asyncio # <-- Необходимый импорт для запуска асинхронной функции

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- БЛОК ИНИЦИАЛИЗАЦИИ И ТОКЕНА ---

# Получаем токен из переменных окружения (безопасный способ)
BOT_TOKEN = os.getenv("BOT_TOKEN") 

# Проверка на случай, если токен не был установлен в настройках Render
if not BOT_TOKEN:
    # Используем logging, а не print, чтобы лог попал в Render
    logging.error("BOT_TOKEN environment variable not set.")
    exit(1)

# --- ОБРАБОТЧИКИ (ХЭНДЛЕРЫ) ---

# Диспетчер обрабатывает сообщения, Бот отправляет их
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Обрабатывает команду /start"""
    await message.answer(f"Привет, {message.from_user.full_name}! Я бот Umi Clean KG.")

# --- ФУНКЦИЯ ЗАПУСКА ---

async def main() -> None:
    """Главная функция для запуска бота"""
    # Запускаем бота, он начинает слушать обновления
    await dp.start_polling(bot)

# --- БЛОК ЗАПУСКА СКРИПТА ---

if __name__ == "__main__":
    # ЭТО ИСПРАВЛЯЕТ IndentationError и запускает асинхронный код
    asyncio.run(main())
