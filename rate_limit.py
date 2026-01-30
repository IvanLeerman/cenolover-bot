import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

from aiogram import Dispatcher, types
from aiogram.dispatcher.middlewares import BaseMiddleware

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 5, window: int = 1):
        super().__init__()
        self.limit = limit  # максимальное количество запросов
        self.window = window  # окно времени в секундах
        self.user_requests: Dict[int, list] = defaultdict(list)

    async def on_pre_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        current_time = time.time()
        
        # Очищаем старые запросы
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if current_time - req_time < self.window
        ]
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.limit:
            await message.answer(
                "⚠️ <b>Слишком много запросов!</b>\n\n"
                "Пожалуйста, подождите несколько секунд.",
                parse_mode="HTML"
            )
            raise Exception("Rate limit exceeded")
        
        # Добавляем новый запрос
        self.user_requests[user_id].append(current_time)

    async def on_pre_process_callback_query(self, callback_query: types.CallbackQuery, data: dict):
        user_id = callback_query.from_user.id
        current_time = time.time()
        
        # Очищаем старые запросы
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if current_time - req_time < self.window
        ]
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.limit:
            await callback_query.answer(
                "Слишком много запросов! Подождите...",
                show_alert=True
            )
            raise Exception("Rate limit exceeded")
        
        # Добавляем новый запрос
        self.user_requests[user_id].append(current_time)

def setup_rate_limit(dp: Dispatcher):
    rate_limit_middleware = RateLimitMiddleware(limit=10, window=1)  # 10 запросов в секунду
    dp.middleware.setup(rate_limit_middleware)
