import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

logger = logging.getLogger(__name__)

async def sync_lots_from_google(db, force_sync: bool = False) -> bool:
    """
    ТЕСТОВАЯ версия - лот на ближайшие 3 минуты
    """
    try:
        # ТЕСТ: лот на ближайшие 3 минуты
        msk_tz = pytz.timezone('Europe/Moscow')
        now_msk = datetime.now(msk_tz)
        start_time_msk = now_msk + timedelta(minutes=3)
        
        google_sheets_data = [
            {
                'auction_id': 3001,
                'name': 'ТЕСТОВЫЙ лот для проверки публикации',
                'article': 'TEST-PUBLISH-001',
                'start_price': 500.00,
                'description': 'Этот лот должен опубликоваться через 3 минуты для проверки работы системы',
                'start_time_msk': start_time_msk.strftime('%H:%M'),
                'start_date': start_time_msk.strftime('%Y-%m-%d')
            }
        ]
        
        added_count = 0
        
        for item in google_sheets_data:
            auction_id = item['auction_id']
            
            # Проверяем существование лота
            existing = await db.get_lot(auction_id)
            
            if not existing:
                # Создаем datetime без временной зоны
                date_str = item['start_date']
                time_str = item['start_time_msk']
                
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                
                # Добавляем новый лот
                await db.create_lot(
                    auction_id=auction_id,
                    name=item['name'],
                    article=item['article'],
                    start_price=item['start_price'],
                    images=[],
                    video_url=None,
                    description=item['description'],
                    start_time=naive_dt
                )
                added_count += 1
                
                logger.info(f"✅ ТЕСТ: Добавлен лот {auction_id}: {item['name']}")
                logger.info(f"   🕐 Старт через 3 минуты: {start_time_msk.strftime('%H:%M МСК')}")
        
        if added_count > 0:
            logger.info(f"🔄 ТЕСТ: Добавлен {added_count} тестовый лот для проверки публикации")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")
        return False

async def check_and_sync_lots(db):
    """Периодическая проверка и синхронизация"""
    logger.info("📥 ТЕСТ: Проверка обновлений...")
    return await sync_lots_from_google(db, force_sync=False)
