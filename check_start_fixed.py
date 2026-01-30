async def check_and_start_lots():
    """Проверяет и запускает лоты, у которых наступило время старта"""
    try:
        upcoming_lots = await db.get_upcoming_lots(hours=1)
        
        for lot in upcoming_lots:
            auction_id = lot['auction_id']
            start_time = lot['start_time']
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            
            # Приводим start_time к той же временной зоне
            if start_time.tzinfo is None:
                # Если время без зоны, считаем что оно в UTC
                start_time = pytz.UTC.localize(start_time)
            
            now = datetime.now(pytz.timezone(TIMEZONE))
            
            # Приводим к одной временной зоне для сравнения
            start_time_in_tz = start_time.astimezone(pytz.timezone(TIMEZONE))
            
            if start_time_in_tz <= now:
                # Запускаем аукцион
                end_time = now + timedelta(hours=AUCTION_DURATION_HOURS)
                await db.set_lot_status(auction_id, 'active')
                await db.set_lot_end_time(auction_id, end_time)
                
                # Публикуем в канал
                lot_info = await db.get_lot(auction_id)
                if lot_info:
                    message_id = await publish_lot_to_channel(auction_id, lot_info)
                    if message_id:
                        await db.set_channel_message_id(auction_id, message_id)
                
                logger.info(f"🚀 Аукцион {auction_id} запущен, закончится в {end_time}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске лотов: {e}")
