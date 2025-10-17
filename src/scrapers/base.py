from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime, timedelta

class BaseScraper(ABC):
    def __init__(self, lookback_hours: int = 6):
        self.lookback_hours = lookback_hours
        self.cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
    
    @abstractmethod
    async def scrape(self) -> List[Dict]:
        """
        Scrape and return list of dicts with:
        {
            'key': str,
            'source_type': str,
            'source_url': str,
            'context': str,
            'found_at': str  # isoformat
        }
        """
        pass
    
    def is_recent(self, timestamp: datetime) -> bool:
        """Check if content is within lookback window"""
        return timestamp >= self.cutoff_time