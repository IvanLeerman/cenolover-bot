# Добавляем обработчик для принудительного запуска
@dp.callback_query_handler(lambda c: c.data == "admin_force_start")
async def cb_admin_force_start(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    # Показываем список лотов для принудительного запуска
    lots = await db.get_active_or_pending_lots()
    
    if not lots:
        await callback.answer("📭 Нет лотов для запуска", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for lot in lots[:10]:
        kb.add(InlineKeyboardButton(
            f"🎯 Лот {lot['auction_id']}: {lot['name'][:20]}...",
            callback_data=f"force_start:{lot['auction_id']}"
        ))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_menu"))
    
    await callback.message.edit_text(
        "🔧 <b>Принудительный запуск аукциона</b>\n\n"
        "Выберите лот для запуска:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("force_start:"))
async def cb_force_start_lot(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    _, auction_id_str = callback.data.split(":")
    auction_id = int(auction_id_str)
    
    # Получаем информацию о лоте
    lot = await db.get_lot(auction_id)
    if not lot:
        await callback.answer("❌ Лот не найден", show_alert=True)
        return
    
    # Принудительно запускаем аукцион
    try:
        await db.set_lot_status(auction_id, 'active')
        end_time = datetime.now(pytz.timezone(TIMEZONE)) + timedelta(hours=AUCTION_DURATION_HOURS)
        await db.set_lot_end_time(auction_id, end_time)
        
        # Публикуем в канал
        message_id = await publish_lot_to_channel(auction_id, lot)
        if message_id:
            await db.set_channel_message_id(auction_id, message_id)
        
        await callback.answer(f"✅ Аукцион {auction_id} запущен!", show_alert=True)
        logger.info(f"👑 Админ {callback.from_user.id} принудительно запустил аукцион {auction_id}")
        
        # Возвращаемся в админ-меню
        await cb_admin_menu(callback)
        
    except Exception as e:
        logger.error(f"❌ Ошибка принудительного запуска: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)
