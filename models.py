import psycopg2
import json
import datetime
import logging
from psycopg2.extras import DictCursor

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_uri: str):
        self.db_uri = db_uri
        self.connection = None
        self.cursor = None
        self.connect()
        self.init_tables()
    
    def connect(self):
        """Устанавливаем соединение с БД"""
        try:
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            
            self.connection = psycopg2.connect(self.db_uri, cursor_factory=DictCursor)
            self.cursor = self.connection.cursor()
            logger.info("✅ Database connected")
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise
    
    def ensure_connection(self):
        """Проверяем и восстанавливаем соединение если нужно"""
        try:
            self.cursor.execute("SELECT 1")
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            logger.warning("⚠️ Database connection lost, reconnecting...")
            self.connect()
    
    def execute(self, query, params=None):
        """Выполнение запроса с проверкой соединения"""
        self.ensure_connection()
        try:
            self.cursor.execute(query, params or ())
            self.connection.commit()
            return self.cursor
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения запроса: {e}")
            self.connection.rollback()
            raise
    
    def fetchone(self, query, params=None):
        """Получить одну строку"""
        self.execute(query, params)
        return self.cursor.fetchone()
    
    def fetchall(self, query, params=None):
        """Получить все строки"""
        self.execute(query, params)
        return self.cursor.fetchall()
    
    # Остальные методы оставляем как в оригинале
    def init_tables(self):
        """Инициализация таблиц если их нет"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                user_name TEXT,
                warnings INTEGER DEFAULT 0,
                banned_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bids (
                id SERIAL PRIMARY KEY,
                auction_id INTEGER REFERENCES lots(auction_id),
                user_id BIGINT,
                amount DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(auction_id, user_id, amount)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                auction_id INTEGER,
                user_id BIGINT,
                amount DECIMAL(10,2),
                payment_status TEXT DEFAULT 'pending',
                payment_id TEXT,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_lots_status ON lots(status);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_lots_end_time ON lots(end_time);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bids_auction_id ON bids(auction_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bids_user_id ON bids(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_payments_payment_id ON payments(payment_id);
            """
        ]

        for table_sql in tables:
            try:
                self.execute(table_sql)
            except Exception as e:
                logger.error(f"❌ Error creating table/index: {e}")

    def upsert_user(self, user_id: int, user_name: str):
        """Добавление/обновление пользователя"""
        self.execute(
            "INSERT INTO users (user_id, user_name) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET user_name = EXCLUDED.user_name",
            (user_id, user_name)
        )

    def get_user(self, user_id: int):
        """Получить пользователя"""
        return self.fetchone("SELECT * FROM users WHERE user_id = %s", (user_id,))

    def lot_exists(self, auction_id: int) -> bool:
        """Проверка существования лота"""
        result = self.fetchone("SELECT 1 FROM lots WHERE auction_id = %s", (auction_id,))
        return bool(result)

    def create_lot(self, **kwargs):
        """Создание лота"""
        columns = []
        values = []
        placeholders = []
        
        for key, value in kwargs.items():
            columns.append(key)
            values.append(value)
            placeholders.append("%s")
        
        sql = f"""
            INSERT INTO lots ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (auction_id) DO UPDATE SET
            {', '.join([f'{col} = EXCLUDED.{col}' for col in columns if col != 'auction_id'])}
        """
        self.execute(sql, tuple(values))
        logger.info(f"📦 Lot created: {kwargs.get('auction_id')} '{kwargs.get('name')}'")

    def get_lot(self, auction_id: int):
        """Получить лот"""
        return self.fetchone("SELECT * FROM lots WHERE auction_id = %s", (auction_id,))

    def get_active_or_pending_lots(self):
        """Получить активные или ожидающие лоты"""
        return self.fetchall(
            "SELECT * FROM lots WHERE status IN ('active', 'pending') ORDER BY start_time"
        )

    def get_finished_lots_to_close(self):
        """Получить завершенные лоты для закрытия"""
        return self.fetchall(
            "SELECT * FROM lots WHERE status = 'active' AND end_time < NOW()"
        )

    def get_bids_desc(self, auction_id: int):
        """Получить ставки по убыванию"""
        return self.fetchall(
            "SELECT * FROM bids WHERE auction_id = %s ORDER BY amount DESC",
            (auction_id,)
        )

    def set_lot_status(self, auction_id: int, status: str):
        """Установка статуса лота"""
        query = "UPDATE lots SET status = %s WHERE auction_id = %s"
        self.execute(query, (status, auction_id))

    def set_lot_end_time(self, auction_id: int, end_time):
        """Установка времени окончания аукциона"""
        query = "UPDATE lots SET end_time = %s WHERE auction_id = %s"
        self.execute(query, (end_time, auction_id))

    def set_channel_message_id(self, auction_id: int, message_id: int):
        """Установка ID сообщения в канале"""
        query = "UPDATE lots SET channel_message_id = %s WHERE auction_id = %s"
        self.execute(query, (message_id, auction_id))
