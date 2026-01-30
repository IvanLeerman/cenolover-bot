async def check_and_close_finished():
    """Проверяет и закрывает завершенные аукционы"""
    try:
        finished_lots = await db.get_finished_lots_to_close()
        
        for lot in finished_lots:
            auction_id = lot['auction_id']
            await close_auction(auction_id)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии аукционов: {e}")

async def close_auction(auction_id: int):
    """Закрытие аукциона и определение победителя"""
    try:
        # Получаем последнюю ставку
        last_bid = await db.get_last_bid(auction_id)
        
        if last_bid:
            winner_id = last_bid['user_id']
            winning_amount = last_bid['amount']
            
            await db.set_winner(auction_id, winner_id)
            await db.set_lot_status(auction_id, 'finished')
            
            # Уведомляем победителя
            try:
                await bot.send_message(
                    winner_id,
                    f"🏆 <b>Поздравляем! Вы выиграли аукцион №{auction_id}</b>\n\n"
                    f"💰 <b>Сумма к оплате:</b> {winning_amount}₽\n"
                    f"⏰ <b>Время на оплату:</b> {PAYMENT_TIMEOUT_MIN} минут\n\n"
                    f"<i>Оплатите через /pay {auction_id}</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить победителя {winner_id}: {e}")
            
            logger.info(f"✅ Аукцион {auction_id} закрыт. Победитель: {winner_id}, сумма: {winning_amount}₽")
        else:
            # Нет ставок - закрываем без победителя
            await db.set_lot_status(auction_id, 'finished')
            logger.info(f"📭 Аукцион {auction_id} закрыт без ставок")
            
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия аукциона {auction_id}: {e}")
async def on_startup(dispatcher: Dispatcher):
    await db.initialize()
    
    # Запускаем планировщик задач
    scheduler.start()
    scheduler.add_job(check_and_start_lots, 'interval', minutes=5)
    scheduler.add_job(check_and_close_finished, 'interval', minutes=1)
    
    logger.info("🚀 Бот «Ценоловер» запущен с Redis storage!")
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>Бот «Ценоловер» успешно запущен!</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"📢 Канал: {AUCTION_CHANNEL}\n"
                f"💾 Хранилище: Redis\n\n"
                "<i>Используйте /start для начала работы</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

async def on_shutdown(dispatcher: Dispatcher):
    # Отменяем все таймеры
    for task in active_timers.values():
        task.cancel()
    if active_timers:
        await asyncio.gather(*active_timers.values(), return_exceptions=True)
    
    await db.close()
    await storage.close()
    logger.info("🛑 Бот «Ценоловер» остановлен")

if __name__ == "__main__":
    # Настройка rate limiting
    setup_rate_limit(dp)
    
    logger.info(f"🚀 Запуск бота «Ценоловер»...")
    logger.info(f"📢 Канал: {AUCTION_CHANNEL}")
    logger.info(f"👑 Админы: {ADMIN_IDS}")
    logger.info(f"💾 Хранилище: Redis")
    
    try:
        executor.start_polling(
            dp,
            skip_updates=True,
            on_startup=on_startup,
            on_shutdown=on_shutdown
        )
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
