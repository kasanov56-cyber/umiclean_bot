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
ADMIN_ID = 952117349 # Ваш проверенный ID

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

# --- ФУНКЦИИ КЛАВИАТУР ---
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

# --- ХЭНДЛЕРЫ КАЛЬКУЛЯТОРА ---
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user.id in selected_extras_storage:
        del selected_extras_storage[message.from_user.id]

    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n\n"
        f"Я — калькулятор клининговой компании **Umi Clean KG**.\n"
        f"Выберите тип уборки для начала расчета:",
        reply_markup=await get_cleaning_type_kb()
    )
    await state.set_state(CleaningStates.choosing_type)


@dp.callback_query(CleaningStates.choosing_type, F.data.startswith("type_"))
async def process_cleaning_type(callback: CallbackQuery, state: FSMContext) -> None:
    base_type_key = callback.data.replace("type_", "")
    await state.update_data(base_type=base_type_key)
    selected_extras_storage[callback.from_user.id] = []
    service_name = await get_service_description(base_type_key)
    
    await callback.message.edit_text(
        f"Вы выбрали **{service_name}**.\n"
        f"Теперь выберите дополнительные услуги (можно выбрать несколько):",
        reply_markup=await get_extras_kb()
    )
    await state.set_state(CleaningStates.choosing_extras)
    await callback.answer()


@dp.callback_query(CleaningStates.choosing_extras, F.data.startswith("extra_"))
async def process_extras_choice(callback: CallbackQuery) -> None:
    extra_key = callback.data.replace("extra_", "")
    user_id = callback.from_user.id
    current_choices = selected_extras_storage.get(user_id, [])
    service_name = await get_service_description(extra_key)

    if extra_key in current_choices:
        current_choices.remove(extra_key)
        message = f"❌ Услуга **{service_name}** удалена."
    else:
        current_choices.append(extra_key)
        message = f"✅ Услуга **{service_name}** добавлена."
        
    selected_extras_storage[user_id] = current_choices
    
    await callback.message.edit_reply_markup(
        reply_markup=await get_extras_kb(current_choices)
    )
    await callback.answer(message)


@dp.callback_query(CleaningStates.choosing_extras, F.data == "calculate_start")
async def start_area_input(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "📝 **Введите площадь** вашего помещения в квадратных метрах (только число). "
        "Например: `45` или `120`."
    )
    await state.set_state(CleaningStates.waiting_for_area)
    await callback.answer()


@dp.message(CleaningStates.waiting_for_area)
async def process_area_and_calculate(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    area_str = message.text.replace(',', '.').strip()
    
    if not re.match(r'^\d+(\.\d+)?$', area_str) or float(area_str) <= 0:
        await message.answer("❌ Пожалуйста, введите **корректное числовое значение** площади (например, 75).")
        return
        
    area = float(area_str)
    
    data = await state.get_data()
    base_type_key = data.get('base_type')
    selected_extras = selected_extras_storage.get(user_id, [])
    
    base_price_m2 = await get_price(base_type_key)
    base_service_name = await get_service_description(base_type_key)
    
    total_cost = base_price_m2 * area
    
    summary_text = f"**Ваш предварительный расчет:**\n\n"
    summary_text += f"**1. Тип уборки:** {base_service_name}\n"
    summary_text += f"   - Площадь: {area:.1f} м²\n"
    summary_text += f"   - Цена за м²: {base_price_m2:.1f} сом\n"
    summary_text += f"   - Базовая стоимость: **{total_cost:.1f} сом**\n\n"
    
    if selected_extras:
        summary_text += "**2. Дополнительные услуги:**\n"
        extras_cost = 0
        
        for extra_key in selected_extras:
            price = await get_price(extra_key)
            service_name = await get_service_description(extra_key)
            
            if 'windows' in extra_key:
                cost = price * area
                extras_cost += cost
                summary_text += f"   - {service_name} ({area:.1f} м²): {cost:.1f} сом\n"
            else:
                cost = price # Фиксированная цена
                extras_cost += cost
                summary_text += f"   - {service_name}: {cost:.1f} сом\n"
            
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

    await state.clear()
    if user_id in selected_extras_storage:
        del selected_extras_storage[user_id]
        
    await message.answer("✅ Расчет завершен. Нажмите /start для нового расчета.")


# --- ХЭНДЛЕРЫ АДМИН-ПАНЕЛИ ---

@dp.message(Command("admin"))
async def admin_start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /admin: открывает панель админа (ТОЛЬКО ДЛЯ АДМИНА)."""
    # ФИНАЛЬНАЯ ПРОВЕРКА: Проверяет, совпадает ли ID отправителя с ADMIN_ID
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещен.")
        return

    await state.clear()
    
    prices = await get_all_prices()
    
    await message.answer(
        "🛠 **АДМИН-ПАНЕЛЬ: Редактирование цен** 🛠\n"
        "Нажмите на услугу, чтобы изменить ее цену:",
        reply_markup=await get_admin_kb(prices)
    )


@dp.callback_query(F.data.startswith("editprice_"))
async def admin_edit_price(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещен.", show_alert=True)
        return

    price_key = callback.data.replace("editprice_", "")
    current_price = await get_price(price_key)
    service_name = await get_service_description(price_key) 
    
    await state.update_data(price_key_to_update=price_key)
    
    await callback.message.edit_text(
        f"Вы выбрали **{service_name}**.\n"
        f"Текущая цена: **{current_price:.1f}** сом.\n\n"
        "📝 **Введите новую числовую цену** (например, `180.5`):"
    )
    await state.set_state(AdminStates.waiting_for_new_price)
    await callback.answer()


@dp.message(AdminStates.waiting_for_new_price)
async def admin_process_new_price(message: Message, state: FSMContext) -> None:
    new_price_str = message.text.replace(',', '.').strip()
    
    if not re.match(r'^\d+(\.\d+)?$', new_price_str) or float(new_price_str) < 0:
        await message.answer("❌ Введите корректное числовое значение цены (не отрицательное).")
        return

    new_price = float(new_price_str)
    
    data = await state.get_data()
    price_key = data.get('price_key_to_update')
    service_name = await get_service_description(price_key)

    success = await update_price(price_key, new_price)

    if success:
        await message.answer(f"✅ Цена для **{service_name}** обновлена на **{new_price:.1f}** сом.")
    else:
        await message.answer("❌ Произошла ошибка при обновлении цены.")

    await state.clear()
    prices = await get_all_prices()
    
    await message.answer(
        "🛠 **АДМИН-ПАНЕЛЬ: Редактирование цен** 🛠\n"
        "Выберите следующую услугу для изменения или закройте:",
        reply_markup=await get_admin_kb(prices)
    )

@dp.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
        
    await state.clear()
    await callback.message.edit_text("Панель администрирования закрыта. Бот работает в режиме калькулятора.")
    await callback.answer()


# --- ФУНКЦИЯ ЗАПУСКА ---

async def main() -> None:
    await init_db()
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
