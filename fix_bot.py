import asyncio
import json
import logging
import pytz
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import (
    API_TOKEN, DB_URI, AUCTION_CHANNEL, TIMEZONE, MIN_STEP,
    AUCTION_DURATION_HOURS, EXTEND_THRESHOLD_MIN, EXTEND_TO_MIN,
    PAYMENT_TIMEOUT_MIN, MAX_UNPAID_WARNINGS, BAN_DAYS, ADMIN_IDS
)
from async_db import AsyncDatabase
from rate_limit import setup_rate_limit
from storage_config import get_redis_storage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auction_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)

# Используем Redis storage вместо MemoryStorage
storage = get_redis_storage()
dp = Dispatcher(bot, storage=storage)

scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
db = AsyncDatabase(DB_URI)

active_timers: Dict[int, asyncio.Task] = {}
