"""
Cache Manager
Handles caching for data and results
"""

import pickle
import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import diskcache
from loguru import logger


class CacheManager:
    """Manages caching across the system"""

    def __init__(self, cache_dir: str = ".cache", max_size: int = 1e9):
        """
        Args:
            cache_dir: Directory for cache storage
            max_size: Maximum cache size in bytes
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize disk cache
        self.cache = diskcache.Cache(str(self.cache_dir), size_limit=int(max_size))
        
        logger.info(f"Cache manager initialized: {cache_dir}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, expire: Optional[int] = None):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds
        """
        try:
            self.cache.set(key, value, expire=expire)
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    def delete(self, key: str):
        """Delete key from cache"""
        try:
            del self.cache[key]
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")

    def clear(self):
        """Clear entire cache"""
        try:
            self.cache.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    def get_or_set(
        self,
        key: str,
        func: Callable,
        expire: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Get from cache or compute and set
        
        Args:
            key: Cache key
            func: Function to call if not in cache
            expire: Expiration time
            args: Positional args for func
            kwargs: Keyword args for func
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        
        if value is not None:
            logger.debug(f"Cache hit: {key}")
            return value
        
        logger.debug(f"Cache miss: {key}, computing...")
        value = func(*args, **kwargs)
        self.set(key, value, expire=expire)
        
        return value

    def memoize(self, expire: Optional[int] = None):
        """
        Decorator for caching function results
        
        Args:
            expire: Expiration time in seconds
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                key = self._make_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                value = self.get(key)
                
                if value is not None:
                    return value
                
                # Compute and cache
                value = func(*args, **kwargs)
                self.set(key, value, expire=expire)
                
                return value
            
            return wrapper
        
        return decorator

    def _make_key(self, prefix: str, args: tuple, kwargs: dict) -> str:
        """
        Create cache key from function name and arguments
        
        Args:
            prefix: Key prefix (function name)
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        # Serialize arguments
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        
        # Create hash
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"

    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            return {
                'size': self.cache.volume(),
                'items': len(self.cache),
                'hits': self.cache.stats(enable=True).get('hits', 0),
                'misses': self.cache.stats(enable=True).get('misses', 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# Global cache instance
_cache = None


def get_cache() -> CacheManager:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def cache_result(expire: Optional[int] = 3600):
    """Decorator for caching function results (convenience function)"""
    cache = get_cache()
    return cache.memoize(expire=expire)
