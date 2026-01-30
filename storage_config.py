import json
from typing import Optional, Any, Dict
from redis import asyncio as aioredis
from aiogram.contrib.fsm_storage.redis import RedisStorage2

class CustomRedisStorage(RedisStorage2):
    async def get_data(self, chat=None, user=None, default=None):
        data = await super().get_data(chat=chat, user=user, default=default)
        # Дополнительная валидация данных
        if data and isinstance(data, dict):
            # Убираем потенциально опасные ключи
            dangerous_keys = ['__class__', '__module__', '__dict__', '__weakref__']
            for key in dangerous_keys:
                data.pop(key, None)
        return data

def get_redis_storage():
    """Создание Redis storage с настройками безопасности"""
    return CustomRedisStorage(
        host='localhost',
        port=6379,
        db=0,
        password=None,  # Если нужен пароль
        prefix='auction_fsm',
        state_ttl=3600,  # 1 час
        data_ttl=1800    # 30 минут
    )
