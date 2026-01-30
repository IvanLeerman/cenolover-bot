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
