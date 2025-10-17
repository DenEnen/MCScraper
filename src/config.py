from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Scraping
    scrape_interval_minutes: int = 30
    lookback_hours: int = 6
    subreddits: str = "PiratedGames,Piracy,CrackWatch"
    forums: str = ""
    
    # Pattern
    key_pattern: str = r"^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
    
    class Config:
        env_file = ".env"
    
    @property
    def subreddit_list(self) -> List[str]:
        return [s.strip() for s in self.subreddits.split(",") if s.strip()]
    
    @property
    def forum_list(self) -> List[str]:
        return [f.strip() for f in self.forums.split(",") if f.strip()]

settings = Settings()