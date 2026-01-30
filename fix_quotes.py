        kb.add(InlineKeyboardButton(
            f"🎯 Лот {lot['auction_id']}: {lot['name'][:20]}...",
            callback_data=f"force_start:{lot['auction_id']}"
