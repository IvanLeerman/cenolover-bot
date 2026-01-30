import logging

logger = logging.getLogger(__name__)

async def run_webhook():
    logger.info("🌐 Вебхук-сервер (режим заглушки)")
    return True
