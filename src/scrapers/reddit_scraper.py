import aiohttp
import asyncio
from datetime import datetime
from typing import List, Dict
from src.scrapers.base import BaseScraper
from src.config import settings
from src.utils import extract_keys

class RedditScraper(BaseScraper):
    def __init__(self, lookback_hours: int = 6):
        super().__init__(lookback_hours)
    
    async def scrape(self) -> List[Dict]:
        """Scrape Reddit for game keys using unauthenticated JSON"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for subreddit_name in settings.subreddit_list:
                try:
                    subreddit_results = await self._scrape_subreddit(session, subreddit_name)
                    results.extend(subreddit_results)
                except Exception as e:
                    print(f"Error scraping r/{subreddit_name}: {e}")
        
        return results
    
    async def _scrape_subreddit(self, session: aiohttp.ClientSession, subreddit_name: str) -> List[Dict]:
        """Scrape a single subreddit"""
        results = []
        seen_keys = set()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit=100"
        
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status != 200:
                return results
            
            data = await response.json()
            posts = data.get('data', {}).get('children', [])
            
            for post in posts:
                post_data = post.get('data', {})
                post_time = datetime.fromtimestamp(post_data.get('created_utc', 0))
                
                if not self.is_recent(post_time):
                    continue
                
                # Check title and selftext
                text = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
                keys = extract_keys(text)
                
                permalink = post_data.get('permalink', '')
                source_url = f"https://reddit.com{permalink}"
                
                for key, context in keys:
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append({
                            'key': key,
                            'source_type': f'reddit-{subreddit_name}',
                            'source_url': source_url,
                            'context': context,
                            'found_at': post_time.isoformat()
                        })
                
                # Fetch comments if post has them
                if post_data.get('num_comments', 0) > 0:
                    comments_url = f"https://www.reddit.com{permalink}.json?limit=50"
                    async with session.get(comments_url, headers=headers, timeout=30) as comm_resp:
                        if comm_resp.status == 200:
                            comm_data = await comm_resp.json()
                            # comm_data[1] is comments
                            comments_listing = comm_data[1].get('data', {}).get('children', [])
                            for comm in comments_listing:
                                comm_body = comm.get('data', {}).get('body', '')
                                comm_time = datetime.fromtimestamp(comm.get('data', {}).get('created_utc', 0))
                                
                                if not self.is_recent(comm_time):
                                    continue
                                
                                keys = extract_keys(comm_body)
                                comm_permalink = comm.get('data', {}).get('permalink', '')
                                comm_url = f"https://reddit.com{comm_permalink}"
                                
                                for key, context in keys:
                                    if key not in seen_keys:
                                        seen_keys.add(key)
                                        results.append({
                                            'key': key,
                                            'source_type': f'reddit-{subreddit_name}',
                                            'source_url': comm_url,
                                            'context': context,
                                            'found_at': comm_time.isoformat()
                                        })
        
        return results