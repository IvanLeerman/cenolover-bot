    async def get_upcoming_lots(self, hours: int = 24) -> List[Dict]:
        """Получение лотов, которые начнутся в ближайшие часы ИЛИ уже должны были начаться"""
        query = """\
SELECT auction_id, name, start_time
FROM lots
WHERE status = 'pending'
AND start_time <= NOW() + INTERVAL '1 hour' * $1
ORDER BY start_time ASC
        """
        return await self.fetchall(query, hours)
