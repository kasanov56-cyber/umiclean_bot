import os
import logging
import asyncio 
import re # Для проверки ввода площади

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем функции для работы с базой данных
from database import init_db, get_price, SERVICE_NAMES

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- КОНФИГУРАЦИЯ ---

BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = 952117349  # <--- ВАЖНО: ЗАМЕНИТЕ 0 НА ВАШ ТЕЛЕГРАМ ID!

if not BOT_TOKEN:
    logging.error("BOT_TOKEN environment variable not set.")
    exit(1)

# --- СОСТОЯНИЯ FSM ДЛЯ КЛИЕНТА (КАЛЬКУЛЯТОР) ---

class CleaningStates(StatesGroup):
    """Состояния для ведения пользователя по шагам калькулятора."""
    choosing_type = State()
    choosing_extras = State()
    waiting_for_area = State()

# --- ОСНОВНАЯ ЛОГИКА ---

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище для выбранных дополнительных услуг (user_id: [extra_key1, extra_key2])
selected_extras_storage = {}


def get_cleaning_type_kb() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора типа уборки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=SERVICE_NAMES['general_cleaning_m2'], callback_data="type_general_cleaning"),
        InlineKeyboardButton(text=SERVICE_NAMES['after_repair_m2'], callback_data="type_after_repair")
    )
    return builder.as_markup()

async def get_extras_kb(current_choices: list = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора дополнительных услуг."""
    builder = InlineKeyboardBuilder()
    
    # Ключи для дополнительных (фиксированных) услуг
    extra_keys = ['windows_price', 'fridge_price', 'oven_price']
    
    for key in extra_keys:
        name = SERVICE_NAMES.get(key, key)
        price = await get_price(key)
        
        # Проверяем, выбрана ли уже эта услуга
        is_selected = key in (current_choices or [])
        
        # Добавляем галочку, если услуга выбрана
        status = "✅ " if is_selected else ""
        
        builder.button(
            text=f"{status}{name} ({price} сом)",
            callback_data=f"extra_{key}"
        )

    builder.row(
        InlineKeyboardButton(text="Продолжить и рассчитать ➡️", callback_data="calculate_start")
    )
    
    # Делаем кнопки в два столбца
    return builder.adjust(1).as_markup()


# --- ХЭНДЛЕРЫ ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start: начинает опрос, предлагает выбор типа уборки."""
    # Очищаем данные FSM и хранилище доп. услуг
    await state.clear()
    if message.from_user.id in selected_extras_storage:
        del selected_extras_storage[message.from_user.id]

    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n\n"
        f"Я — калькулятор клининговой компании **Umi Clean KG**.\n"
        f"Выберите тип уборки для начала расчета:",
        reply_markup=get_cleaning_type_kb()
    )
    # Переводим пользователя в состояние выбора типа
    await state.set_state(CleaningStates.choosing_type)


@dp.callback_query(CleaningStates.choosing_type, F.data.startswith("type_"))
async def process_cleaning_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора типа уборки."""
    base_type_key = callback.data.replace("type_", "")
    
    # Сохраняем базовый тип уборки в FSM-контексте
    await state.update_data(base_type=base_type_key)
    
    # Инициализируем хранилище выбранных доп. услуг
    selected_extras_storage[callback.from_user.id] = []
    
    await callback.message.edit_text(
        f"Вы выбрали **{SERVICE_NAMES.get(f'{base_type_key}_m2')}**.\n"
        f"Теперь выберите дополнительные услуги (можно выбрать несколько):",
        reply_markup=await get_extras_kb()
    )
    # Переводим пользователя в состояние выбора дополнительных услуг
    await state.set_state(CleaningStates.choosing_extras)
    await callback.answer()


@dp.callback_query(CleaningStates.choosing_extras, F.data.startswith("extra_"))
async def process_extras_choice(callback: CallbackQuery) -> None:
    """Обработка нажатия на дополнительную услугу (включение/выключение)."""
    extra_key = callback.data.replace("extra_", "")
    user_id = callback.from_user.id
    
    # Получаем текущий список выбранных услуг
    current_choices = selected_extras_storage.get(user_id, [])
    
    # Логика переключения (toggle)
    if extra_key in current_choices:
        current_choices.remove(extra_key)
        message = f"❌ Услуга **{SERVICE_NAMES.get(extra_key)}** удалена."
    else:
        current_choices.append(extra_key)
        message = f"✅ Услуга **{SERVICE_NAMES.get(extra_key)}** добавлена."
        
    selected_extras_storage[user_id] = current_choices
    
    # Обновляем клавиатуру, чтобы показать/скрыть галочку
    await callback.message.edit_reply_markup(
        reply_markup=await get_extras_kb(current_choices)
    )
    await callback.answer(message)


@dp.callback_query(CleaningStates.choosing_extras, F.data == "calculate_start")
async def start_area_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход к вводу площади."""
    await callback.message.edit_text(
        "📝 **Введите площадь** вашего помещения в квадратных метрах (только число). "
        "Например: `45` или `120`."
    )
    # Переводим пользователя в состояние ожидания ввода площади
    await state.set_state(CleaningStates.waiting_for_area)
    await callback.answer()


@dp.message(CleaningStates.waiting_for_area)
async def process_area_and_calculate(message: Message, state: FSMContext) -> None:
    """Обработка введенной площади и финальный расчет."""
    user_id = message.from_user.id
    area_str = message.text.replace(',', '.').strip()
    
    # Проверка, что введенное значение — это положительное число
    if not re.match(r'^\d+(\.\d+)?$', area_str) or float(area_str) <= 0:
        await message.answer("❌ Пожалуйста, введите **корректное числовое значение** площади (например, 75).")
        return
        
    area = float(area_str)
    
    # 1. Получаем данные из FSM и хранилища
    data = await state.get_data()
    base_type_key = data.get('base_type')
    selected_extras = selected_extras_storage.get(user_id, [])
    
    # 2. Получаем цены из базы
    base_price_m2 = await get_price(f'{base_type_key}_m2')
    
    # 3. Расчет базовой стоимости
    total_cost = base_price_m2 * area
    
    # Формируем итоговое сообщение и список выбранных услуг
    summary_text = f"**Ваш предварительный расчет:**\n\n"
    summary_text += f"**1. Тип уборки:** {SERVICE_NAMES.get(f'{base_type_key}_m2')}\n"
    summary_text += f"   - Площадь: {area:.1f} м²\n"
    summary_text += f"   - Цена за м²: {base_price_m2:.1f} сом\n"
    summary_text += f"   - Базовая стоимость: **{total_cost:.1f} сом**\n\n"
    
    # 4. Расчет стоимости дополнительных услуг
    if selected_extras:
        summary_text += "**2. Дополнительные услуги:**\n"
        extras_cost = 0
        
        for extra_key in selected_extras:
            price = await get_price(extra_key)
            extras_cost += price
            summary_text += f"   - {SERVICE_NAMES.get(extra_key)}: {price:.1f} сом\n"
            
        total_cost += extras_cost
        summary_text += f"\n   - Стоимость доп. услуг: **{extras_cost:.1f} сом**\n"
    else:
        summary_text += "2. Дополнительные услуги: **не выбраны.**\n"
        
    summary_text += f"\n💰 **ИТОГО:** {total_cost:.1f} сом\n\n"
    summary_text += (
        f"**Внимание!** Этот расчет является предварительным. "
        f"Для точной оценки свяжитесь с нашим менеджером."
    )
    
    await message.answer(summary_text)

    # Очищаем состояние и хранилище доп. услуг после расчета
    await state.clear()
    if user_id in selected_extras_storage:
        del selected_extras_storage[user_id]
        
    # Предлагаем начать заново
    await message.answer("✅ Расчет завершен. Нажмите /start для нового расчета.")


# --- ФУНКЦИЯ ЗАПУСКА ---

async def main() -> None:
    """Главная функция для запуска бота."""
    # Инициализируем базу данных перед запуском бота
    await init_db()
    
    # Запускаем бота
    logging.info("Starting bot...")
    await dp.start_polling(bot)

# --- БЛОК ЗАПУСКА СКРИПТА ---

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by KeyboardInterrupt")
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
