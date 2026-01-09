import os
import logging
import asyncio
from typing import List, Tuple

# Импорты aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импорт базы данных (Убедитесь, что database.py находится в той же папке)
from database import init_db, get_base_services, get_addon_services, get_price, update_price, get_all_prices

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- КОНСТАНТЫ И ТОКЕН ---

# Установите ваш ID для админ-панели (ЗАМЕНИТЕ НУЛЕМ НА ВАШ АЙДИ ТЕЛЕГРАМ)
ADMIN_ID = 0  # <--- ВАШ ID ПОЛЬЗОВАТЕЛЯ

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN environment variable not set.")
    exit(1)

# Диспетчер и Бот
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- КОНЕЧНЫЙ АВТОМАТ (FSM) ДЛЯ КЛИЕНТА ---

class CleaningStates(StatesGroup):
    """Состояния для клиента в процессе расчета"""
    TYPE_SELECTION = State()
    AREA_INPUT = State()
    ADDONS_SELECTION = State()
    RESULT = State()

# --- 1. КЛАВИАТУРЫ ---

async def get_base_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора основного вида уборки."""
    builder = InlineKeyboardBuilder()
    services: List[Tuple[str, str]] = await get_base_services()
    
    for key, description in services:
        builder.button(text=description, callback_data=f"base_{key}")
        
    builder.adjust(1)
    return builder.as_markup()

async def get_addons_keyboard(current_addons: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора дополнительных услуг."""
    builder = InlineKeyboardBuilder()
    addons = await get_addon_services()
    
    for key, description, price in addons:
        # Отмечаем выбранные услуги
        is_selected = "✅" if key in current_addons else ""
        button_text = f"{is_selected}{description} ({int(price)} сом)"
        builder.button(text=button_text, callback_data=f"addon_{key}")

    # Кнопка завершения выбора
    builder.button(text="✔️ Завершить выбор и посчитать", callback_data="calculate_final")
    
    builder.adjust(1)
    return builder.as_markup()

# --- 2. ОБРАБОТЧИКИ ДЛЯ КЛИЕНТА ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Начинает процесс расчета."""
    await state.clear()
    await state.set_state(CleaningStates.TYPE_SELECTION)
    
    welcome_text = (
        f"Здравствуйте, {message.from_user.full_name}!\n"
        "Я — калькулятор клининговых услуг Umi Clean KG.\n\n"
        "**Выберите, пожалуйста, вид уборки:**"
    )
    await message.answer(welcome_text, reply_markup=await get_base_keyboard())

@dp.callback_query(F.data.startswith("base_"), CleaningStates.TYPE_SELECTION)
async def select_base_service(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор основного вида уборки."""
    base_key = callback.data.split("_")[1]
    base_price = await get_price(base_key)
    
    await state.update_data(
        base_service_key=base_key,
        base_price_m2=base_price,
        addons=[] # Инициализация списка доп. услуг
    )
    
    await state.set_state(CleaningStates.AREA_INPUT)
    
    await callback.message.edit_text(
        "**✅ Вид уборки выбран.**\n"
        "Теперь введите площадь помещения **в квадратных метрах (м²)**.\n\n"
        "*(Например: 55)*"
    )
    await callback.answer()

@dp.message(CleaningStates.AREA_INPUT)
async def input_area_handler(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод площади."""
    try:
        area = float(message.text.replace(',', '.').strip())
        if area <= 0:
            raise ValueError
        
        await state.update_data(area=area)
        await state.set_state(CleaningStates.ADDONS_SELECTION)
        
        addons_text = (
            "**✅ Площадь принята.**\n"
            "Выберите дополнительные услуги (по желанию). "
            "Нажмите на услугу, чтобы добавить/удалить ее из заказа.\n"
            "Когда закончите, нажмите кнопку **'Завершить выбор и посчитать'**."
        )
