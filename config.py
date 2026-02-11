import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # @cenolover
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# Database
DB_URI = os.getenv("DB_URI")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Auction settings
AUCTION_DURATION_HOURS = int(os.getenv("AUCTION_DURATION_HOURS", 12))
EXTEND_TIME_MINUTES = int(os.getenv("EXTEND_TIME_MINUTES", 10))
PAYMENT_TIME_MINUTES = int(os.getenv("PAYMENT_TIME_MINUTES", 15))

# Paths
QR_CODE_DIR = "qr_codes"
LOG_DIR = "logs"
