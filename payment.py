import logging
from typing import Tuple
from io import BytesIO

logger = logging.getLogger(__name__)

async def generate_payment_url(auction_id: int, user_id: int, amount: float) -> Tuple[str, str]:
    """Генерация платежной ссылки (заглушка)"""
    logger.info(f"💳 Генерация платежа: аукцион {auction_id}, пользователь {user_id}, сумма {amount}₽")
    payment_id = f"pay_{auction_id}_{user_id}"
    payment_url = f"https://example.com/pay/{payment_id}"
    return payment_url, payment_id

async def check_payment_status(payment_id: str) -> str:
    """Проверка статуса платежа (заглушка)"""
    logger.info(f"🔍 Проверка статуса платежа: {payment_id}")
    return "succeeded"

async def generate_qr(payment_url: str) -> BytesIO:
    """Генерация QR-кода (заглушка)"""
    logger.info(f"🖼 Генерация QR-кода для: {payment_url}")
    return BytesIO(b"QR_CODE_STUB")
