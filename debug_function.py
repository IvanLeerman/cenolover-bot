async def check_and_start_lots():
    """Проверяет и запускает лоты, у которых наступило время старта"""
    try:
        upcoming_lots = await db.get_upcoming_lots(hours=1)
        logger.info(f"🔍 Найдено лотов для проверки: {len(upcoming_lots)}")
        
        for lot in upcoming_lots:
            auction_id = lot['auction_id']
            start_time = lot['start_time']
            logger.info(f"🔍 Проверяем лот {auction_id}: start_time={start_time}, type={type(start_time)}")
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
                logger.info(f"📅 Конвертирован из строки: {start_time}")
            
            # Приводим start_time к той же временной зоне
            if start_time.tzinfo is None:
                # Если время без зоны, считаем что оно в UTC
                start_time = pytz.UTC.localize(start_time)
                logger.info(f"🌐 Добавлена UTC зона: {start_time}")
            
            now = datetime.now(pytz.timezone(TIMEZONE))
            logger.info(f"⏰ Текущее время ({TIMEZONE}): {now}")
            
            # Приводим к одной временной зоне для сравнения
            start_time_in_tz = start_time.astimezone(pytz.timezone(TIMEZONE))
            logger.info(f"🔄 Конвертировано во время ({TIMEZONE}): {start_time_in_tz}")
            
            logger.info(f"⚖️ Сравнение: {start_time_in_tz} <= {now} = {start_time_in_tz <= now}")
            
            if start_time_in_tz <= now:
                logger.info(f"🚀 Запускаем аукцион {auction_id}")
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
                
                logger.info(f"✅ Аукцион {auction_id} запущен, закончится в {end_time}")
            else:
                logger.info(f"⏳ Аукцион {auction_id} еще не готов к запуску")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске лотов: {e}")
