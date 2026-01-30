import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

async def fetch_base_lots() -> List[Dict]:
    logger.info("📥 Загрузка лотов из Google Sheets")
    return []

async def append_report_row(auction_id, name, article, start_price, final_price, status):
    logger.info(f"📝 Запись в отчет: аукцион {auction_id}, статус {status}")
