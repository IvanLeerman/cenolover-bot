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
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
db = AsyncDatabase(DB_URI)

active_timers: Dict[int, asyncio.Task] = {}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def format_dt(dt: datetime | None) -> str:
    if not dt:
        return "не задано"
    return dt.strftime("%d.%m.%Y %H:%M")

async def format_remaining(end_time: datetime | None) -> str:
    if not end_time:
        return "---"
    now = datetime.now(pytz.timezone(TIMEZONE))
    delta = end_time - now
    if delta.total_seconds() <= 0:
        return "🛑 Завершён"
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours} ч {minutes:02d} мин"
    elif minutes > 0:
        return f"{minutes} мин {seconds:02d} сек"
    else:
        return f"{seconds} сек"

# ========== STATES ==========
class BidState(StatesGroup):
    amount = State()

# ========== HANDLERS ==========

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.full_name
        await db.upsert_user(user_id, user_name)

        user = await db.get_user(user_id)
        banned_text = ""
        if user and user.get('banned_until'):
            banned_until = user.get('banned_until')
            if isinstance(banned_until, str):
                banned_until = datetime.fromisoformat(banned_until)
            if banned_until > datetime.now():
                banned_text = f"\n\n⚠️ <b>Вы заблокированы до {format_dt(banned_until)}</b>"

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🏆 Активные аукционы", callback_data="view_auctions"),
            InlineKeyboardButton("💼 Мои аукционы", callback_data="my_auctions"),
            InlineKeyboardButton("📜 Правила", callback_data="help"),
            InlineKeyboardButton("👑 Админ-панель", callback_data="admin_menu")
        )

        welcome_text = (
            f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
            f"🚀 <i>Это бот-аукцион «Ценоловер»</i> - здесь вы можете участвовать в увлекательных торгах "
            f"за уникальные товары по выгодным ценам.{banned_text}\n\n"
            f"🎯 <b>Выберите действие:</b>"
        )

        await message.answer(welcome_text, reply_markup=kb, parse_mode="HTML")
        logger.info(f"👤 Пользователь {user_id} ({user_name}) запустил бота")

    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@dp.callback_query_handler(lambda c: c.data == "help")
async def cb_help(callback: types.CallbackQuery):
    rules_text = (
        "📋 <b>Правила аукциона «Ценоловер»:</b>\n\n"
        f"🎯 <b>Минимальный шаг ставки:</b> {MIN_STEP}₽\n"
        f"⏰ <b>Длительность аукциона:</b> {AUCTION_DURATION_HOURS} часов\n"
        f"🔄 <b>Автопродление:</b> Если до конца менее {EXTEND_THRESHOLD_MIN} минут и приходит новая ставка, "
        f"аукцион продлевается на {EXTEND_TO_MIN} минут\n"
        f"💳 <b>Оплата:</b> У победителя есть {PAYMENT_TIMEOUT_MIN} минут на оплату\n"
        f"⚠️ <b>Важно:</b> При неоплате аукцион возобновляется, а неоплативший получает предупреждение\n"
        f"🔒 <b>Блокировка:</b> {MAX_UNPAID_WARNINGS} предупреждения = блокировка на {BAN_DAYS} дней\n\n"
        "<i>Удачных торгов! 🍀</i>"
    )
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(rules_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "view_auctions")
async def cb_view_auctions(callback: types.CallbackQuery):
    try:
        lots = await db.get_active_or_pending_lots()
        
        if not lots:
            no_lots_text = (
                "📭 <b>Активных аукционов нет</b>\n\n"
                "<i>Следите за обновлениями в канале - новые аукционы появляются регулярно!</i>"
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            await callback.message.edit_text(no_lots_text, reply_markup=kb, parse_mode="HTML")
            return
        
        text = "🏆 <b>Актуальные аукционы «Ценоловер»:</b>\n\n"
        for i, lot in enumerate(lots[:5], 1):
            status_emoji = "🟢" if lot['status'] == 'active' else "⏳"
            status_text = "Активен" if lot['status'] == 'active' else "Ожидает старта"
            
            text += (
                f"{status_emoji} <b>Аукцион №{lot['auction_id']}</b>\n"
                f"📦 <i>{lot['name']}</i>\n"
                f"💰 <b>Текущая цена:</b> {lot['current_price']}₽\n"
                f"📊 <b>Статус:</b> {status_text}\n"
            )
            
            if lot['status'] == 'active':
                text += f"🎯 <b>Действует:</b> <code>Нажмите 'Участвовать'</code>\n"
            else:
                text += f"⏰ <b>Старт:</b> <code>Скоро</code>\n"
            text += "─" * 20 + "\n"
        
        if len(lots) > 5:
            text += f"\n📊 <i>И еще {len(lots)-5} аукционов...</i>"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎯 Выбрать аукцион", callback_data="join_menu"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка просмотра аукционов: {e}")
        await callback.message.answer("❌ Ошибка загрузки аукционов")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "join_menu")
async def cb_join_menu(callback: types.CallbackQuery):
    try:
        lots = await db.get_active_or_pending_lots()
        active_lots = [lot for lot in lots if lot['status'] == 'active']
        
        if not active_lots:
            await callback.answer("🎯 Сейчас нет активных аукционов", show_alert=True)
            return
        
        kb = InlineKeyboardMarkup(row_width=1)
        for lot in active_lots[:10]:
            kb.add(InlineKeyboardButton(
                f"🎯 Аукцион №{lot['auction_id']}: {lot['name'][:30]}...",
                callback_data=f"join:{lot['auction_id']}"
            ))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="view_auctions"))
        
        await callback.message.edit_text(
            "🎯 <b>Выберите аукцион для участия:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка выбора аукциона: {e}")
        await callback.answer("❌ Ошибка")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("join:"))
async def cb_join_auction(callback: types.CallbackQuery):
    """Обработка нажатия кнопки участия в аукционе"""
    try:
        user_id = callback.from_user.id
        user_name = callback.from_user.full_name
        
        # Получаем auction_id из callback_data
        _, auction_id_str = callback.data.split(":")
        auction_id = int(auction_id_str)
        
        # Добавляем пользователя в БД
        await db.upsert_user(user_id, user_name)
        
        # Проверяем бан пользователя
        user = await db.get_user(user_id)
        if user and user.get('banned_until'):
            banned_until = user.get('banned_until')
            if isinstance(banned_until, str):
                banned_until = datetime.fromisoformat(banned_until)
            if banned_until > datetime.now():
                await callback.answer("🚫 Вы заблокированы для участия", show_alert=True)
                return
        
        # Проверяем существование лота
        lot = await db.get_lot(auction_id)
        if not lot:
            await callback.answer("❌ Аукцион не найден", show_alert=True)
            return
            
        if lot['status'] != 'active':
            await callback.answer("⏳ Аукцион еще не начался", show_alert=True)
            return
        
        # Отправляем сообщение пользователю
        await callback.message.answer(
            f"✅ <b>Вы присоединились к аукциону №{auction_id}!</b>\n\n"
            f"📦 <b>Товар:</b> {lot['name']}\n"
            f"💰 <b>Текущая цена:</b> {lot['current_price']}₽\n\n"
            f"⚡ <b>Сделайте ставку:</b>\n"
            f"Отправьте <code>/bid {auction_id} СУММА</code>\n"
            f"<i>Минимальная ставка: {float(lot['current_price']) + MIN_STEP}₽</i>\n\n"
            f"📊 <b>Следите за аукционом:</b>\n"
            f"<a href='https://t.me/{AUCTION_CHANNEL[1:]}/{lot.get('channel_message_id', '')}'>Перейти в канал →</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        await callback.answer("✅ Вы присоединились к аукциону")
        
    except Exception as e:
        logger.error(f"❌ Ошибка присоединения к аукциону: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.message_handler(commands=["bid"])
async def cmd_bid(message: types.Message):
    """Обработка команды /bid"""
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.answer(
                "❌ <b>Неверный формат команды</b>\n\n"
                "✅ <b>Используйте:</b>\n"
                "<code>/bid НОМЕР_АУКЦИОНА СУММА</code>\n\n"
                "<i>Пример:</i> <code>/bid 123 1500</code>",
                parse_mode="HTML"
            )
            return
        
        auction_id = int(args[1])
        amount = float(args[2])
        user_id = message.from_user.id
        user_name = message.from_user.full_name
        
        # Проверяем бан пользователя
        user = await db.get_user(user_id)
        if user and user.get('banned_until'):
            banned_until = user.get('banned_until')
            if isinstance(banned_until, str):
                banned_until = datetime.fromisoformat(banned_until)
            if banned_until > datetime.now():
                await message.answer(f"🚫 Вы заблокированы для участия до {format_dt(banned_until)}")
                return
        
        # Получаем лот
        lot = await db.get_lot(auction_id)
        if not lot:
            await message.answer("❌ Аукцион не найден")
            return
            
        if lot['status'] != 'active':
            await message.answer("⏳ Этот аукцион не активен")
            return
        
        # Добавляем ставку
        success = await db.add_bid_transaction(auction_id, user_id, amount)
        
        if success:
            # Обновляем время окончания, если нужно
            end_time = lot.get('end_time')
            if end_time:
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time)
                
                now = datetime.now(pytz.timezone(TIMEZONE))
                time_left = (end_time - now).total_seconds() / 60
                
                if time_left < EXTEND_THRESHOLD_MIN:
                    new_end_time = now + timedelta(minutes=EXTEND_TO_MIN)
                    await db.set_lot_end_time(auction_id, new_end_time)
                    logger.info(f"⏰ Аукцион {auction_id} продлен до {new_end_time}")
            
            # Уведомляем участников
            await notify_participants(auction_id, user_id, amount)
            
            await message.answer(
                f"✅ <b>Ваша ставка принята!</b>\n\n"
                f"🎯 <b>Аукцион №{auction_id}</b>\n"
                f"📦 <b>Товар:</b> {lot['name']}\n"
                f"💰 <b>Ваша ставка:</b> {amount}₽\n\n"
                f"<i>Следите за аукционом, вас могут перебить!</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Ставка не принята</b>\n\n"
                f"💰 <b>Текущая цена:</b> {lot['current_price']}₽\n"
                f"🎯 <b>Минимальная ставка:</b> {float(lot['current_price']) + MIN_STEP}₽\n\n"
                f"<i>Сделайте ставку выше текущей цены + минимальный шаг</i>",
                parse_mode="HTML"
            )
            
    except ValueError:
        await message.answer("❌ Неверный формат числа. Используйте: /bid НОМЕР СУММА")
    except Exception as e:
        logger.error(f"❌ Ошибка в /bid: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@dp.callback_query_handler(lambda c: c.data == "my_auctions")
async def cb_my_auctions(callback: types.CallbackQuery):
    """Мои аукционы (где я участвую или выиграл)"""
    try:
        user_id = callback.from_user.id
        
        # Получаем все ставки пользователя
        query = """\
SELECT DISTINCT b.auction_id, l.name, l.current_price, l.status, 
       l.winner_user_id, MAX(b.amount) as my_bid
FROM bids b
JOIN lots l ON b.auction_id = l.auction_id
WHERE b.user_id = $1
GROUP BY b.auction_id, l.name, l.current_price, l.status, l.winner_user_id
ORDER BY l.end_time DESC
LIMIT 20
        """
        
        async with db.pool.acquire() as conn:
            my_lots = await conn.fetch(query, user_id)
        
        if not my_lots:
            text = (
                "📭 <b>Вы еще не участвовали в аукционах</b>\n\n"
                "<i>Присоединяйтесь к активным аукционам и делайте ставки!</i>"
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🏆 К аукционам", callback_data="view_auctions"))
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        
        text = "💼 <b>Мои аукционы:</b>\n\n"
        for lot in my_lots:
            status_icon = "🟢" if lot['status'] == 'active' else "🟡" if lot['status'] == 'finished' else "⚪"
            status_text = "Активен" if lot['status'] == 'active' else "Завершен" if lot['status'] == 'finished' else "Ожидает"
            
            is_winner = lot['winner_user_id'] == user_id
            winner_text = "🏆 <b>Вы победитель!</b>" if is_winner else ""
            
            text += (
                f"{status_icon} <b>Аукцион №{lot['auction_id']}</b>\n"
                f"📦 {lot['name']}\n"
                f"💰 <b>Текущая цена:</b> {lot['current_price']}₽\n"
                f"🎯 <b>Моя ставка:</b> {lot['my_bid']}₽\n"
                f"📊 <b>Статус:</b> {status_text} {winner_text}\n"
                f"─" * 20 + "\n"
            )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🏆 К аукционам", callback_data="view_auctions"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки моих аукционов: {e}")
        await callback.message.answer("❌ Ошибка загрузки")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_main")
async def cb_back_to_main(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    welcome_text = (
        f"👋 <b>С возвращением, {user_name}!</b>\n\n"
        f"🎯 <b>«Ценоловер» - аукцион выгодных цен</b>\n\n"
        f"🏆 <b>Выберите действие:</b>"
    )
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🏆 Активные аукционы", callback_data="view_auctions"),
        InlineKeyboardButton("💼 Мои аукционы", callback_data="my_auctions"),
        InlineKeyboardButton("📜 Правила", callback_data="help"),
        InlineKeyboardButton("👑 Админ-панель", callback_data="admin_menu")
    )
    
    await callback.message.edit_text(welcome_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_menu")
async def cb_admin_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    admin_text = (
        "👑 <b>Панель администратора «Ценоловер»</b>\n\n"
        "⚙️ <b>Доступные действия:</b>"
    )
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton("📦 Управление лотами", callback_data="admin_lots"),
        InlineKeyboardButton("🔄 Синхронизация", callback_data="admin_sync"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    )
    
    await callback.message.edit_text(admin_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# ========== УВЕДОМЛЕНИЯ ==========

async def notify_participants(auction_id: int, new_bidder_id: int, amount: float):
    """Уведомление всех участников аукциона о новой ставке"""
    try:
        participants = await db.get_participants(auction_id)
        lot = await db.get_lot(auction_id)
        
        if not lot or not participants:
            return
        
        notification_text = (
            f"🔔 <b>Новая ставка на аукционе №{auction_id}</b>\n\n"
            f"📦 <b>Товар:</b> {lot['name']}\n"
            f"💰 <b>Новая цена:</b> {amount}₽\n\n"
            f"<i>Вашу ставку перебили! Сделайте новую ставку выше текущей.</i>"
        )
        
        for participant in participants:
            user_id = participant['user_id']
            if user_id == new_bidder_id:
                continue
                
            try:
                await bot.send_message(user_id, notification_text, parse_mode="HTML")
                logger.info(f"📨 Уведомление отправлено участнику {user_id} по аукциону {auction_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомлений: {e}")

# ========== АВТОМАТИЧЕСКИЕ ЗАДАЧИ ==========

