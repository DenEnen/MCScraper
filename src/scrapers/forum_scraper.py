import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime
from src.scrapers.base import BaseScraper
from src.config import settings
from src.utils import extract_keys

class ForumScraper(BaseScraper):
    def __init__(self, lookback_hours: int = 6):
        super().__init__(lookback_hours)
    
    async def scrape(self) -> List[Dict]:
        """Scrape forums for game keys"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for forum_url in settings.forum_list:
                try:
                    forum_results = await self._scrape_forum(session, forum_url)
                    results.extend(forum_results)
                except Exception as e:
                    print(f"Error scraping {forum_url}: {e}")
        
        return results
    
    async def _scrape_forum(self, session: aiohttp.ClientSession, url: str) -> List[Dict]:
        """Scrape a single forum - basic implementation, fetches main page and extracts keys.
        Note: For better coverage, consider adding thread crawling in future iterations."""
        results = []
        seen_keys = set()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    return results
                
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                
                # Extract all text content
                text_content = soup.get_text()
                keys = extract_keys(text_content)
                
                # Determine forum type from URL
                forum_type = self._get_forum_type(url)
                
                current_time = datetime.utcnow()
                
                for key, context in keys:
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append({
                            'key': key,
                            'source_type': forum_type,
                            'source_url': url,
                            'context': context,
                            'found_at': current_time.isoformat()
                        })
        
        except Exception as e:
            print(f"Forum scrape error for {url}: {e}")
        
        return results
    
    def _get_forum_type(self, url: str) -> str:
        """Extract forum type from URL"""
        if 'cs.rin.ru' in url:
            return 'cs.rin.ru'
        elif 'nulled.to' in url:
            return 'nulled.to'
        elif 'pirates-forum.org' in url:
            return 'suprBay'
        elif 'mpgh.net' in url:
            return 'mpgh.net'
        elif 'nullforums.net' in url:
            return 'nullforums.net'
        elif 'mydigitallife.net' in url:
            return 'mydigitallife'
        elif 'serials.ws' in url:
            return 'serials.ws'
        elif 'cracked.to' in url:
            return 'cracked.to'
        elif 'mobilism.org' in url:
            return 'mobilism'
        return 'forum'