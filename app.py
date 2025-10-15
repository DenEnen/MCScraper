from flask import Flask, jsonify, request
import requests
import praw
from prawcore import NotFound, Forbidden, ServerError
import threading
import time
import re
import logging
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from typing import List, Dict, Optional
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
class Config:
    # Reddit API credentials
    REDDIT_CLIENT_ID = '4OAIj60JZ6sBLk074QClow'
    REDDIT_CLIENT_SECRET = 'eWVjp5q0Ue5uXDIFWySK-ujUMRx1Rw'
    REDDIT_USER_AGENT = 'KeyScraperBot/1.0 (by u/yourusername)'

    # Scraping config
    SCRAPE_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    CACHE_DURATION = 300  # 5 minutes cache
    MAX_POSTS = 100  # Maximum posts to fetch per request
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

config = Config()

# Simple cache implementation
class SimpleCache:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}

    def get(self, key):
        if key in self.cache:
            if datetime.now() - self.timestamps[key] < timedelta(seconds=config.CACHE_DURATION):
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = datetime.now()

cache = SimpleCache()

def get_reddit_client():
    """Initialize and return Reddit API client"""
    try:
        reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT
        )
        # Test connection
        reddit.user.me()
        return reddit
    except Exception as e:
        logger.error(f"Failed to initialize Reddit client: {e}")
        logger.info("Using read-only Reddit client")
        # Return read-only instance for public data
        return praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
            check_for_async=False
        )

def get_session():
    """Create a requests session with proper headers"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': config.USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })
    return session

def is_valid_key_format(text: str, pattern: str = None) -> bool:
    """
    Validate key format with customizable pattern.
    Default pattern matches format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    if not text or not isinstance(text, str):
        return False

    if pattern is None:
        # Default Minecraft-like key pattern
        pattern = r'^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$'

    return bool(re.match(pattern, text.strip()))

def extract_keys_from_text(text: str) -> List[str]:
    """Extract potential keys from text content"""
    if not text:
        return []
    # Pattern to find keys in text
    pattern = r'\b[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}\b'
    matches = re.findall(pattern, text)
    return [key for key in matches if is_valid_key_format(key)]

def scrape_reddit_api(subreddit_name: str, limit: int = config.MAX_POSTS,
                      time_filter: str = 'day', sort: str = 'new') -> List[Dict]:
    """
    Scrape Reddit using official API (PRAW)

    Args:
        subreddit_name: Name of subreddit to scrape
        limit: Maximum number of posts to fetch (default: 100)
        time_filter: Time filter - 'hour', 'day', 'week', 'month', 'year', 'all'
        sort: Sort method - 'hot', 'new', 'top', 'rising'
    """
    keys_data = []

    try:
        reddit = get_reddit_client()
        subreddit = reddit.subreddit(subreddit_name)

        # Get posts based on sort method
        if sort == 'hot':
            posts = subreddit.hot(limit=limit)
        elif sort == 'new':
            posts = subreddit.new(limit=limit)
        elif sort == 'top':
            posts = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort == 'rising':
            posts = subreddit.rising(limit=limit)
        else:
            posts = subreddit.new(limit=limit)

        for post in posts:
            try:
                # Extract keys from title
                title_keys = extract_keys_from_text(post.title)

                # Extract keys from selftext (for text posts)
                body_keys = extract_keys_from_text(post.selftext) if hasattr(post, 'selftext') else []

                # Combine all keys found
                all_keys = title_keys + body_keys

                # Also check top-level comments
                if hasattr(post, 'comments'):
                    try:
                        post.comments.replace_more(limit=0)  # Don't expand "load more comments"
                        for comment in post.comments[:10]:  # Check top 10 comments
                            comment_keys = extract_keys_from_text(comment.body)
                            all_keys.extend(comment_keys)
                    except Exception as e:
                        logger.debug(f"Error reading comments: {e}")

                # Add metadata for each key found
                for key in set(all_keys):  # Remove duplicates within post
                    keys_data.append({
                        'key': key,
                        'source': f"r/{subreddit_name}",
                        'post_title': post.title[:100],  # Truncate long titles
                        'post_url': f"https://reddit.com{post.permalink}",
                        'post_score': post.score,
                        'post_created': datetime.fromtimestamp(post.created_utc).isoformat(),
                        'found_at': datetime.now().isoformat()
                    })

            except Exception as e:
                logger.debug(f"Error processing post: {e}")
                continue

        logger.info(f"Scraped r/{subreddit_name}, found {len(keys_data)} keys from {limit} posts")

    except NotFound:
        logger.error(f"Subreddit r/{subreddit_name} not found")
    except Forbidden:
        logger.error(f"Access forbidden to r/{subreddit_name}")
    except ServerError as e:
        logger.error(f"Reddit server error: {e}")
    except Exception as e:
        logger.error(f"Error scraping Reddit via API: {e}")

    return keys_data

def scrape_multiple_subreddits(subreddits: List[str], limit_per_sub: int = 50) -> List[Dict]:
    """Scrape multiple subreddits and combine results"""
    all_keys = []

    for subreddit in subreddits:
        keys = scrape_reddit_api(subreddit, limit=limit_per_sub)
        all_keys.extend(keys)
        time.sleep(1)  # Small delay between subreddits

    return all_keys

def scrape_forum(url: str) -> List[Dict]:
    """Scrape a forum for Minecraft keys"""
    session = get_session()
    keys_data = []

    try:
        response = session.get(url, timeout=config.SCRAPE_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Example: Scraping keys from a specific HTML structure
        for element in soup.find_all('div', class_='key-container'):
            key = element.get_text(strip=True)
            if key and is_valid_key_format(key):
                keys_data.append({
                    'key': key,
                    'source': url,
                    'found_at': datetime.now().isoformat()
                })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping {url}: {e}")

    return keys_data

def scrape_keys(url: str) -> List[Dict]:
    if 'reddit.com' in url:
        subreddit = url.split('/r/')[1].split('/')[0]
        return scrape_reddit_api(subreddit)
    else:
        return scrape_forum(url)

@app.route('/scrape', methods=['GET'])
def scrape():
    """
    API endpoint to scrape subreddits for keys

    Query parameters:
    - subreddit: Single subreddit name (e.g., 'gaming')
    - subreddits: Comma-separated list of subreddits (e.g., 'gaming,pcgaming')
    - limit: Number of posts per subreddit (default: 100, max: 1000)
    - sort: Sort method - 'hot', 'new', 'top', 'rising' (default: 'new')
    - time_filter: For 'top' sort - 'hour', 'day', 'week', 'month', 'year', 'all'
    """
    try:
        # Check if Reddit API is configured
        if not config.REDDIT_CLIENT_ID or not config.REDDIT_CLIENT_SECRET:
            return jsonify({
                'error': 'Reddit API not configured',
                'message': 'Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables',
                'instructions': 'Get credentials from https://www.reddit.com/prefs/apps'
            }), 500

        # Get parameters
        subreddit_param = request.args.get('subreddit', '')
        subreddits_param = request.args.get('subreddits', '')
        limit = min(int(request.args.get('limit', 100)), 1000)
        sort = request.args.get('sort', 'new')
        time_filter = request.args.get('time_filter', 'day')

        # Determine which subreddits to scrape
        if subreddits_param:
            subreddits = [s.strip() for s in subreddits_param.split(',')]
        elif subreddit_param:
            subreddits = [subreddit_param]
        else:
            subreddits = ['gaming']  # Default

        # Create cache key
        cache_key = f"scrape_{'-'.join(subreddits)}_{limit}_{sort}_{time_filter}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info("Returning cached results")
            return jsonify({
                'keys': cached_result,
                'count': len(cached_result),
                'cached': True,
                'subreddits': subreddits,
                'timestamp': datetime.now().isoformat()
            })

        # Scrape subreddits
        if len(subreddits) == 1:
            all_keys = scrape_reddit_api(
                subreddits[0],
                limit=limit,
                time_filter=time_filter,
                sort=sort
            )
        else:
            limit_per_sub = limit // len(subreddits)
            all_keys = scrape_multiple_subreddits(subreddits, limit_per_sub)

        # Remove duplicate keys (keep first occurrence)
        seen = set()
        unique_keys = []
        for key_data in all_keys:
            if key_data['key'] not in seen:
                seen.add(key_data['key'])
                unique_keys.append(key_data)

        # Cache results
        cache.set(cache_key, unique_keys)

        logger.info(f"Scraping completed. Found {len(unique_keys)} unique keys")

        return jsonify({
            'keys': unique_keys,
            'count': len(unique_keys),
            'cached': False,
            'subreddits': subreddits,
            'parameters': {
                'limit': limit,
                'sort': sort,
                'time_filter': time_filter
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API documentation"""
    return jsonify({
        'name': 'Reddit Key Scraper API',
        'version': '2.0',
        'description': 'Scrapes Reddit using official API (PRAW) to find game keys',
        'endpoints': {
            '/scrape': {
                'method': 'GET',
                'description': 'Scrape subreddits for keys',
                'parameters': {
                    'subreddit': 'Single subreddit name (e.g., gaming)',
                    'subreddits': 'Comma-separated list (e.g., gaming,pcgaming)',
                    'limit': 'Posts per subreddit (default: 100, max: 1000)',
                    'sort': 'hot, new, top, or rising (default: new)',
                    'time_filter': 'For top sort: hour, day, week, month, year, all'
                },
                'examples': [
                    '/scrape?subreddit=gaming&limit=50',
                    '/scrape?subreddits=gaming,pcgaming&sort=top&time_filter=week',
                    '/scrape?subreddit=FreeGameFindings&limit=200&sort=new'
                ]
            },
            '/health': {
                'method': 'GET',
                'description': 'Health check endpoint'
            }
        },
        'setup': {
            'required_env_vars': [
                'REDDIT_CLIENT_ID',
                'REDDIT_CLIENT_SECRET',
                'REDDIT_USER_AGENT (optional)',
                'BASE_URL (for keep-alive)'
            ],
            'get_credentials': 'https://www.reddit.com/prefs/apps'
        },
        'note': 'This scraper uses Reddit\'s official API and respects rate limits'
    })

def keep_alive():
    """Keep-alive thread to prevent service from sleeping on free tier hosting"""
    # Wait for server to start
    time.sleep(30)

    base_url = os.environ.get('BASE_URL', 'https://mcscraper.onrender.com')

    while True:
        try:
            # Use health endpoint instead of scrape to avoid unnecessary load
            response = requests.get(f'{base_url}/health', timeout=10)
            if response.status_code == 200:
                logger.info("Keep-alive ping successful")
            else:
                logger.warning(f"Keep-alive returned status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Keep-alive request failed: {e}")

        # Sleep for 14 minutes (free tier services often sleep after 15 min)
        time.sleep(60 * 14)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'

    # Start the keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("Keep-alive thread started")

    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
