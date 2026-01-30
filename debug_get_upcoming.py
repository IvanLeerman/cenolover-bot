    async def get_upcoming_lots(self, hours: int = 24) -> List[Dict]:
        """ОТЛАДОЧНАЯ версия с логированием"""
        import logging
        logger = logging.getLogger(__name__)
        
        query = """
SELECT auction_id, name, start_time
FROM lots
WHERE status = 'pending'
AND start_time <= NOW() + INTERVAL '1 hour' * $1
ORDER BY start_time ASC
        """
        
        logger.info(f"🔍 DEBUG get_upcoming_lots: hours={hours}, query={query}")
        
        try:
            result = await self.fetchall(query, hours)
            logger.info(f"🔍 DEBUG: Найдено {len(result)} лотов")
            for lot in result:
                logger.info(f"🔍 DEBUG Лот: id={lot['auction_id']}, start_time={lot['start_time']}, type={type(lot['start_time'])}")
            return result
        except Exception as e:
            logger.error(f"❌ DEBUG Ошибка в get_upcoming_lots: {e}")
            return []
