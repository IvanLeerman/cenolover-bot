# ========== ФУНКЦИЯ ПУБЛИКАЦИИ В КАНАЛ ==========

async def publish_lot_to_channel(auction_id: int, lot_info: dict):
    """Публикация лота в канал"""
    try:
        name = lot_info.get('name', 'Неизвестно')
        article = lot_info.get('article', 'Не указан')
        price = float(lot_info.get('current_price', 0))
        description = lot_info.get('description', '')
        
        caption = (
            f"🎯 <b>Аукцион №{auction_id}</b>\n\n"
            f"📦 <b>Товар:</b> {name}\n"
            f"📋 <b>Артикул:</b> {article}\n"
            f"💰 <b>Стартовая цена:</b> {price}₽\n\n"
            f"📝 <b>Описание:</b>\n{description}\n\n"
            f"👇 <i>Нажмите кнопку ниже для участия</i>"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎯 Участвовать в аукционе", 
                                    callback_data=f"join:{auction_id}"))
        
        # Отправляем в канал
        from config import AUCTION_CHANNEL
        from aiogram import Bot
        from config import API_TOKEN
        
        bot = Bot(token=API_TOKEN)
        message = await bot.send_message(
            AUCTION_CHANNEL,
            caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Лот {auction_id} опубликован в канал")
        return message.message_id
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Ошибка публикации лота {auction_id}: {e}")
        return None
