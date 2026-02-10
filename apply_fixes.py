import re

# Читаем асинхронный bot.py
with open('/home/auctionbot/app/bot.py', 'r') as f:
    content = f.read()

# 1. Находим функцию start_auction и добавляем проверку channel_message_id
start_auction_pattern = r'(async def start_auction\(auction_id: int\):.*?status = lot\.get\(\'status\'\))'
start_auction_replacement = r'''async def start_auction(auction_id: int):
    """Перевод лота в active, установка end_time и публикация в канал."""
    try:
        logger.info(f"🚀 Запуск аукциона {auction_id}")
        lot = db.get_lot(auction_id)
        if not lot:
            logger.warning(f"❌ Попытка стартовать несуществующий аукцион {auction_id}")
            return

        status = lot.get('status')
        channel_message_id = lot.get("channel_message_id")
        if channel_message_id:
            logger.info(f"ℹ️ Лот {auction_id} уже опубликован (message_id: {channel_message_id})")
            # Если лот завершен, но не опубликован - не публикуем
            if status != "active":
                db.set_lot_status(auction_id, "active")
            return'''

content = re.sub(start_auction_pattern, start_auction_replacement, content, flags=re.DOTALL)

# 2. Находим функцию publish_lot_to_channel и заменяем ее
# Сначала найдем оригинальную функцию (она будет отличаться от синхронной)
publish_pattern = r'async def publish_lot_to_channel\(auction_id: int, lot\):.*?async def'

# Берем исправленную версию из контейнера
with open('/home/auctionbot/backups/app_container_backup_20260209_175610/bot.py', 'r') as f:
    container_content = f.read()

# Извлекаем исправленную функцию publish_lot_to_channel из контейнера
container_publish_match = re.search(r'async def publish_lot_to_channel\(auction_id: int, lot\):.*?async def notify_participants_new_bid', 
                                   container_content, re.DOTALL)

if container_publish_match:
    fixed_publish_function = container_publish_match.group(0).replace('async def notify_participants_new_bid', '')
    
    # Заменяем в асинхронной версии
    content = re.sub(publish_pattern, fixed_publish_function, content, flags=re.DOTALL)

# Записываем обратно
with open('/home/auctionbot/app/bot.py', 'w') as f:
    f.write(content)

print("✅ Исправления применены к асинхронной версии")
