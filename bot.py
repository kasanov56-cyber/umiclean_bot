import os
import logging
import asyncio 
import re 

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    init_db, 
    get_price, 
    get_all_prices, 
    update_price, 
    get_base_services, 
    get_addon_services, 
    get_service_description 
)


# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- КОНФИГУРАЦИЯ ---

BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = 952117349 # Ваш текущий ID (который мы проверим)

if not BOT_TOKEN:
    logging.error("BOT_TOKEN environment variable not set.")
    exit(1)

# --- СОСТОЯНИЯ FSM ---
class CleaningStates(StatesGroup):
    choosing_type = State()
    choosing_extras = State()
    waiting_for_area = State()

class AdminStates(StatesGroup):
    waiting_for_new_price = State()
    price_key_to_update = State() 

# --- ОСНОВНАЯ ЛОГИКА ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
selected_extras_storage = {}

# --- ФУНКЦИИ КЛАВИАТУР (оставлены без изменений) ---
async def get_cleaning_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    base_services = await get_base_services() 
    for key, description in base_services:
        builder.button(text=description, callback_data=f"type_{key}")
    return builder.adjust(2).as_markup()

async def get_extras_kb(current_choices: list = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    addon_services = await get_addon_services() 
    for key, description, price in addon_services:
        is_selected = key in (current_choices or [])
        status = "✅ " if is_selected else ""
        builder.button(text=f"{status}{description} ({price:.0f} сом)", callback_data=f"extra_{key}")
    builder.row(InlineKeyboardButton(text="Продолжить и рассчитать ➡️", callback_data="calculate_start"))
    return builder.adjust(1).as_markup()

async def get_admin_kb(prices_list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value, desc in prices_list:
        builder.button(text=f"{desc}: {value:.1f} сом", callback_data=f"editprice_{key}")
    builder.row(InlineKeyboardButton(text="❌ Закрыть панель", callback_data="admin_close"))
    return builder.adjust(1).as_markup()

# --- ХЭНДЛЕРЫ КАЛЬКУЛЯТОРА (оставлены без изменений) ---
# ... (оставьте все хэндлеры от command_start_handler до process_area_and_calculate без изменений) ...


# --- ВРЕМЕННЫЙ ХЭНДЛЕР АДМИН-ПАНЕЛИ ДЛЯ ПРОВЕРКИ ID ---

@dp.message(Command("admin"))
async def admin_start_handler(message: Message, state: FSMContext) -> None:
    """
    ВНИМАНИЕ! Этот код временно показывает ваш фактический ID.
    Если ваш ID в переменной ADMIN_ID не совпадает с фактическим,
    вы увидите 'Доступ запрещен', но получите верный ID.
    """
    
    # 1. Отправляем ID обратно
    await message.answer(f"Ваш ID, который видит бот: {message.from_user.id}")

    # 2. Если ID не совпадает с ADMIN_ID, запрещаем доступ
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещен. Используйте ID выше для исправления ADMIN_ID.")
        return

    # 3. Если ID совпадает, запускаем админку
    await state.clear()
    prices = await get_all_prices()
    
    await message.answer(
        "🛠 **АДМИН-ПАНЕЛЬ: Редактирование цен** 🛠\n"
        "Нажмите на услугу, чтобы изменить ее цену:",
        reply_markup=await get_admin_kb(prices)
    )

# --- ОСТАЛЬНЫЕ ХЭНДЛЕРЫ АДМИН-ПАНЕЛИ (оставлены без изменений) ---
# ... (оставьте все хэндлеры от admin_edit_price до admin_close без изменений) ...

# --- ФУНКЦИЯ ЗАПУСКА (оставлена без изменений) ---

async def main() -> None:
    await init_db()
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by KeyboardInterrupt")
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
