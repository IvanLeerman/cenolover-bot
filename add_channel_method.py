    async def set_channel_message_id(self, auction_id: int, message_id: int):
        """Сохраняем ID сообщения в канале для последующего обновления"""
        query = "UPDATE lots SET channel_message_id = $1 WHERE auction_id = $2"
        await self.execute(query, message_id, auction_id)
