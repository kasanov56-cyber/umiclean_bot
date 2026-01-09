# bot.py (УПРОЩЁННАЯ ВЕРСИЯ — только клиентская часть)
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


BOT_TOKEN = "@umiclean_bot" 8153807753:AAExY7hoDryEu9IxO_Ln_Vz-FuHQZrgdlqA
ADMIN_CHAT_ID = 952117349 
