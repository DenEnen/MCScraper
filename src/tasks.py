from celery import Celery
from celery.schedules import crontab
from datetime import datetime
import asyncio
import redis
import json

from src.config import settings
from src.scrapers.reddit_scraper import RedditScraper
from src.scrapers.forum_scraper import ForumScraper

# Initialize Celery
celery_app = Celery(
    'tasks',
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Schedule scraping
celery_app.conf.beat_schedule = {
    'scrape-all-sources': {
        'task': 'src.tasks.scrape_all',
        'schedule': crontab(minute=f'*/{settings.scrape_interval_minutes}'),
    },
}

@celery_app.task(name='src.tasks.scrape_all')
def scrape_all():
    """Main scraping task"""
    asyncio.run(scrape_all_async())

async def scrape_all_async():
    """Async scraping logic"""
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    
    try:
        all_keys = []
        
        # Scrape Reddit
        try:
            reddit_scraper = RedditScraper(lookback_hours=settings.lookback_hours)
            reddit_keys = await reddit_scraper.scrape()
            all_keys.extend(reddit_keys)
            print(f"Reddit: Found {len(reddit_keys)} keys")
        except Exception as e:
            print(f"Reddit scraper error: {e}")
        
        # Scrape Forums
        if settings.forum_list:
            try:
                forum_scraper = ForumScraper(lookback_hours=settings.lookback_hours)
                forum_keys = await forum_scraper.scrape()
                all_keys.extend(forum_keys)
                print(f"Forums: Found {len(forum_keys)} keys")
            except Exception as e:
                print(f"Forum scraper error: {e}")
        
        # Save new keys to Redis
        new_keys_count = 0
        for key_data in all_keys:
            key_value = key_data['key']
            if not r.hexists('keys_data', key_value):
                r.hset('keys_data', key_value, json.dumps(key_data))
                r.lpush('keys_list', key_value)  # Add to front of list for recent first
                new_keys_count += 1
        
        print(f"Scrape completed: {new_keys_count} new keys saved")
        
    except Exception as e:
        print(f"Scrape failed: {e}")
        raise

@celery_app.task(name='src.tasks.keep_alive')
def keep_alive():
    """Keep-alive ping task"""
    print(f"Keep-alive ping at {datetime.utcnow()}")
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

# Schedule keep-alive every 10 minutes
celery_app.conf.beat_schedule['keep-alive'] = {
    'task': 'src.tasks.keep_alive',
    'schedule': crontab(minute='*/10'),
}