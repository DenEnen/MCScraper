import re
from typing import List, Tuple
from src.config import settings

def extract_keys(text: str) -> List[Tuple[str, str]]:
    """
    Extract game keys from text and return with context.
    Returns: List of (key, context) tuples
    """
    if not text:
        return []
    
    pattern = re.compile(settings.key_pattern)
    results = []
    
    # Find all matches with their positions
    for match in pattern.finditer(text):
        key = match.group(0)
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end].strip()
        
        # Clean context
        context = ' '.join(context.split())
        if len(context) > 200:
            context = context[:200] + "..."
        
        results.append((key, context))
    
    return results

def is_valid_key(key: str) -> bool:
    """Validate key format"""
    return bool(re.match(settings.key_pattern, key))