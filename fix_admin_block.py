    kb = InlineKeyboardMarkup(row_width=1)
    for lot in lots[:10]:
        kb.add(InlineKeyboardButton(
            f"🎯 Лот {lot['auction_id']}: {lot['name'][:20]}...",
            callback_data=f"force_start:{lot['auction_id']}"
        ))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_menu"))
