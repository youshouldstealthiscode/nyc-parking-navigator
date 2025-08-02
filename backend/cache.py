"""
Caching layer for performance optimization
"""
import json
import hashlib
from typing import Optional, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import redis
from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CacheManager:
    """Manages caching with Redis or in-memory fallback"""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if available"""
        if settings.redis_url:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self.redis_client = None
    
    def _generate_key(self, prefix: str, params: dict) -> str:
        """Generate cache key from prefix and parameters"""
        # Sort params for consistent keys
        sorted_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"{prefix}:{param_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                # Memory cache with expiration check
                if key in self.memory_cache:
                    data, expiry = self.memory_cache[key]
                    if datetime.now() < expiry:
                        return data
                    else:
                        del self.memory_cache[key]
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        ttl = ttl or settings.cache_ttl
        
        try:
            serialized = json.dumps(value)
            
            if self.redis_client:
                return self.redis_client.setex(key, ttl, serialized)
            else:
                # Memory cache with expiration
                expiry = datetime.now() + timedelta(seconds=ttl)
                self.memory_cache[key] = (value, expiry)
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
            else:
                # Memory cache pattern matching
                keys_to_delete = [k for k in self.memory_cache.keys() 
                                 if pattern.replace('*', '') in k]
                for key in keys_to_delete:
                    del self.memory_cache[key]
                return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
        return 0
    
    def clear_expired(self):
        """Clear expired entries from memory cache"""
        if not self.redis_client:
            now = datetime.now()
            expired_keys = [k for k, (_, exp) in self.memory_cache.items() if exp < now]
            for key in expired_keys:
                del self.memory_cache[key]


# Global cache instance
cache = CacheManager()


def cached(prefix: str, ttl: int = None):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_params = {
                "args": str(args),
                "kwargs": str(kwargs)
            }
            cache_key = cache._generate_key(prefix, cache_params)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {prefix}")
                return cached_result
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {prefix}, result cached")
            
            return result
        return wrapper
    return decorator