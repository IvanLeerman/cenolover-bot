import asyncio
import json
import datetime
import logging
from typing import List, Dict, Optional, Any
import asyncpg
from asyncpg.pool import Pool

from config import MIN_STEP

logger = logging.getLogger(__name__)

class AsyncDatabase:
    def __init__(self, db_uri: str):
        self.db_uri = db_uri
        self.pool: Optional[Pool] = None

    async def initialize(self):
        """Инициализация пула соединений"""
        self.pool = await asyncpg.create_pool(self.db_uri, min_size=5, max_size=20)
        await self.init_tables()
        logger.info("✅ Database pool initialized")

    async def close(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Database pool closed")

    async def execute(self, query: str, *args):
        """Выполнение запроса"""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                return await connection.execute(query, *args)

    async def fetchone(self, query: str, *args) -> Optional[Dict]:
        """Получение одной записи"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchall(self, query: str, *args) -> List[Dict]:
        """Получение всех записей"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def init_tables(self):
        """Инициализация таблиц с транзакционностью"""
        tables = [
            """\
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    user_name TEXT,
    warnings INTEGER DEFAULT 0,
    banned_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)\
            """,
            """\
CREATE TABLE IF NOT EXISTS lots (
    auction_id INTEGER PRIMARY KEY,
    name TEXT,
    article TEXT,
    start_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    images TEXT,
    video_url TEXT,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT DEFAULT 'pending',
    winner_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel_message_id BIGINT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)\
            """,
            """\
CREATE TABLE IF NOT EXISTS bids (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER REFERENCES lots(auction_id) ON DELETE CASCADE,
    user_id BIGINT,
    amount DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(auction_id, user_id, amount)
)\
            """,
            """\
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER,
    user_id BIGINT,
    amount DECIMAL(10,2),
    payment_status TEXT DEFAULT 'pending',
    payment_id TEXT,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)\
            """,
            """\
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    auction_id INTEGER,
    notification_type TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)\
            """,
        ]

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id);",
            "CREATE INDEX IF NOT EXISTS idx_lots_status ON lots(status);",
            "CREATE INDEX IF NOT EXISTS idx_lots_end_time ON lots(end_time);",
            "CREATE INDEX IF NOT EXISTS idx_bids_auction_id ON bids(auction_id);",
            "CREATE INDEX IF NOT EXISTS idx_bids_user_id ON bids(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_payments_payment_id ON payments(payment_id);",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_auction ON notifications(user_id, auction_id);"
        ]

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for table_sql in tables:
                    await connection.execute(table_sql)
                for index_sql in indexes:
                    await connection.execute(index_sql)

    # --- Users ---
    async def upsert_user(self, user_id: int, user_name: str):
        query = """\
INSERT INTO users (user_id, user_name)
VALUES ($1, $2)
ON CONFLICT (user_id) DO UPDATE SET user_name = EXCLUDED.user_name\
        """
        await self.execute(query, user_id, user_name)

    async def get_user(self, user_id: int) -> Optional[Dict]:
        query = "SELECT * FROM users WHERE user_id = $1"
        return await self.fetchone(query, user_id)

    async def add_warning_auto_ban(self, user_id: int, ban_days: int):
        """Атомарная операция: предупреждение + бан при необходимости"""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                user = await connection.fetchrow(
                    "SELECT warnings FROM users WHERE user_id = $1 FOR UPDATE",
                    user_id
                )
                if not user:
                    return

                warnings = user['warnings'] + 1
                banned_until = None

                if warnings >= 3:
                    banned_until = datetime.datetime.now() + datetime.timedelta(days=ban_days)

                await connection.execute(
                    "UPDATE users SET warnings = $1, banned_until = $2 WHERE user_id = $3",
                    warnings, banned_until, user_id
                )

    async def set_ban(self, user_id: int, until: Optional[datetime.datetime]):
        query = "UPDATE users SET banned_until = $1 WHERE user_id = $2"
        await self.execute(query, until, user_id)

    async def increment_warning(self, user_id: int):
        query = "UPDATE users SET warnings = warnings + 1 WHERE user_id = $1"
        await self.execute(query, user_id)

    # --- Lots ---
    async def lot_exists(self, auction_id: int) -> bool:
        query = "SELECT 1 FROM lots WHERE auction_id = $1"
        result = await self.fetchone(query, auction_id)
        return result is not None

    async def create_lot(self, auction_id: int, name: str, article: str, start_price: float,
                        images: List[str], video_url: Optional[str], description: str,
                        start_time: datetime.datetime):
        query = """\
INSERT INTO lots (auction_id, name, article, start_price, current_price,
                 images, video_url, description, start_time, status)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')\
        """
        images_json = json.dumps(images)
        await self.execute(
            query, auction_id, name, article, start_price, start_price,
            images_json, video_url, description, start_time
        )

    async def set_lot_status(self, auction_id: int, status: str):
        query = "UPDATE lots SET status = $1 WHERE auction_id = $2"
        await self.execute(query, status, auction_id)

    async def set_lot_end_time(self, auction_id: int, end_time: datetime.datetime):
        query = "UPDATE lots SET end_time = $1 WHERE auction_id = $2"
        await self.execute(query, end_time, auction_id)

    async def get_lot(self, auction_id: int) -> Optional[Dict]:
        query = "SELECT * FROM lots WHERE auction_id = $1"
        return await self.fetchone(query, auction_id)

    async def update_current_price(self, auction_id: int, amount: float):
        query = "UPDATE lots SET current_price = $1 WHERE auction_id = $2"
        await self.execute(query, amount, auction_id)

    async def set_channel_message_id(self, auction_id: int, message_id: int):
        """Сохраняем ID сообщения в канале для последующего обновления"""
        query = "UPDATE lots SET channel_message_id = $1 WHERE auction_id = $2"
        await self.execute(query, message_id, auction_id)
    async def set_winner(self, auction_id: int, user_id: Optional[int]):
        query = "UPDATE lots SET winner_user_id = $1 WHERE auction_id = $2"
        await self.execute(query, user_id, auction_id)

    async def get_active_or_pending_lots(self) -> List[Dict]:
        query = """\
SELECT auction_id, name, current_price, status
FROM lots
WHERE status IN ('pending','active')
ORDER BY start_time ASC\
        """
        return await self.fetchall(query)

    async def get_finished_lots_to_close(self) -> List[Dict]:
        query = """\
SELECT auction_id FROM lots
WHERE status = 'active' AND end_time IS NOT NULL AND end_time <= NOW()\
        """
        return await self.fetchall(query)

    async def get_upcoming_lots(self, hours: int = 24) -> List[Dict]:
        """Получение лотов, которые начнутся в ближайшие часы ИЛИ уже должны были начаться"""
        query = """\
SELECT auction_id, name, start_time
FROM lots
WHERE status = 'pending'
AND start_time <= NOW() + INTERVAL '1 hour' * $1
ORDER BY start_time ASC
        """
        return await self.fetchall(query, hours)

    async def set_channel_message_id(self, auction_id: int, message_id: int):
        """Установка ID сообщения в канале"""
        query = "UPDATE lots SET channel_message_id = $1 WHERE auction_id = $2"
        await self.execute(query, message_id, auction_id)

    async def set_lot_end_time(self, auction_id: int, end_time):
        """Установка времени окончания аукциона"""
        query = "UPDATE lots SET end_time = $1 WHERE auction_id = $2"
        await self.execute(query, end_time, auction_id)

    async def set_lot_status(self, auction_id: int, status: str):
        """Установка статуса лота"""
        query = "UPDATE lots SET status = $1 WHERE auction_id = $2"
        await self.execute(query, status, auction_id)

    async def fetchrow(self, query: str, *args):
        """Выполнить запрос и вернуть одну строку"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

