"""
缓存管理系统
支持内存缓存、分布式缓存、缓存策略
"""

import time
import threading
import pickle
import hashlib
from typing import Any, Optional, Dict, Callable, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import OrderedDict
from enum import Enum


class CachePolicy(Enum):
    """缓存策略"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def touch(self):
        """更新访问时间和计数"""
        self.accessed_at = datetime.now()
        self.access_count += 1


class CacheStats:
    """缓存统计"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self.errors = 0
        self._lock = threading.Lock()

    def record_hit(self):
        """记录命中"""
        with self._lock:
            self.hits += 1

    def record_miss(self):
        """记录未命中"""
        with self._lock:
            self.misses += 1

    def record_set(self):
        """记录设置"""
        with self._lock:
            self.sets += 1

    def record_delete(self):
        """记录删除"""
        with self._lock:
            self.deletes += 1

    def record_eviction(self):
        """记录驱逐"""
        with self._lock:
            self.evictions += 1

    def record_error(self):
        """记录错误"""
        with self._lock:
            self.errors += 1

    def get_hit_rate(self) -> float:
        """获取命中率"""
        with self._lock:
            total = self.hits + self.misses
            return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "deletes": self.deletes,
                "evictions": self.evictions,
                "errors": self.errors,
                "hit_rate": self.get_hit_rate()
            }

    def reset(self):
        """重置统计"""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.sets = 0
            self.deletes = 0
            self.evictions = 0
            self.errors = 0


class MemoryCache:
    """内存缓存"""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[int] = None,
        policy: CachePolicy = CachePolicy.LRU
    ):
        """
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL（秒）
            policy: 缓存策略
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.policy = policy
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值或默认值
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.record_miss()
                return default

            # 检查是否过期
            if entry.is_expired():
                self._cache.pop(key)
                self._stats.record_miss()
                return default

            # 更新访问信息
            entry.touch()

            # LRU策略：移到末尾
            if self.policy == CachePolicy.LRU:
                self._cache.move_to_end(key)

            self._stats.record_hit()
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），None表示使用默认值
        """
        with self._lock:
            # 检查是否需要驱逐
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict()

            # 创建缓存条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                accessed_at=datetime.now(),
                ttl_seconds=ttl if ttl is not None else self.default_ttl
            )

            self._cache[key] = entry

            # LRU策略：新条目放在末尾
            if self.policy == CachePolicy.LRU:
                self._cache.move_to_end(key)

            self._stats.record_set()

    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
                self._stats.record_delete()
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def _evict(self):
        """驱逐一个缓存条目"""
        if not self._cache:
            return

        if self.policy == CachePolicy.LRU:
            # 删除最久未使用的（第一个）
            self._cache.popitem(last=False)
        elif self.policy == CachePolicy.LFU:
            # 删除访问次数最少的
            key_to_evict = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
            self._cache.pop(key_to_evict)
        elif self.policy == CachePolicy.FIFO:
            # 删除最先进入的（第一个）
            self._cache.popitem(last=False)
        else:
            # 默认删除第一个
            self._cache.popitem(last=False)

        self._stats.record_eviction()

    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                self._cache.pop(key)
                self._stats.record_eviction()

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats.to_dict(),
            "size": len(self._cache),
            "max_size": self.max_size,
            "policy": self.policy.value
        }

    def reset_stats(self):
        """重置统计"""
        self._stats.reset()


class CacheManager:
    """缓存管理器 - 统一管理多个缓存实例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._caches: Dict[str, MemoryCache] = {}
            self._default_cache = MemoryCache(max_size=1000, default_ttl=300)
            self._lock = threading.RLock()
            self._initialized = True

    def create_cache(
        self,
        name: str,
        max_size: int = 1000,
        default_ttl: Optional[int] = None,
        policy: CachePolicy = CachePolicy.LRU
    ) -> MemoryCache:
        """
        创建命名缓存

        Args:
            name: 缓存名称
            max_size: 最大大小
            default_ttl: 默认TTL
            policy: 缓存策略

        Returns:
            MemoryCache实例
        """
        with self._lock:
            if name in self._caches:
                return self._caches[name]

            cache = MemoryCache(max_size, default_ttl, policy)
            self._caches[name] = cache
            return cache

    def get_cache(self, name: str) -> Optional[MemoryCache]:
        """
        获取命名缓存

        Args:
            name: 缓存名称

        Returns:
            MemoryCache实例或None
        """
        return self._caches.get(name)

    def get_default_cache(self) -> MemoryCache:
        """获取默认缓存"""
        return self._default_cache

    def delete_cache(self, name: str) -> bool:
        """
        删除命名缓存

        Args:
            name: 缓存名称

        Returns:
            是否成功删除
        """
        with self._lock:
            if name in self._caches:
                self._caches.pop(name)
                return True
            return False

    def clear_all(self):
        """清空所有缓存"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            self._default_cache.clear()

    def cleanup_all_expired(self) -> Dict[str, int]:
        """
        清理所有过期条目

        Returns:
            每个缓存清理的条目数
        """
        result = {}
        with self._lock:
            for name, cache in self._caches.items():
                count = cache.cleanup_expired()
                if count > 0:
                    result[name] = count

            count = self._default_cache.cleanup_expired()
            if count > 0:
                result["default"] = count

        return result

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存的统计信息"""
        stats = {}
        with self._lock:
            for name, cache in self._caches.items():
                stats[name] = cache.get_stats()
            stats["default"] = self._default_cache.get_stats()
        return stats


# 全局缓存管理器
_global_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    return _global_cache_manager


# 便捷函数

def cache_get(key: str, cache_name: Optional[str] = None, default: Any = None) -> Any:
    """获取缓存值"""
    manager = get_cache_manager()
    cache = manager.get_cache(cache_name) if cache_name else manager.get_default_cache()
    return cache.get(key, default)


def cache_set(key: str, value: Any, ttl: Optional[int] = None, cache_name: Optional[str] = None):
    """设置缓存值"""
    manager = get_cache_manager()
    cache = manager.get_cache(cache_name) if cache_name else manager.get_default_cache()
    cache.set(key, value, ttl)


def cache_delete(key: str, cache_name: Optional[str] = None) -> bool:
    """删除缓存值"""
    manager = get_cache_manager()
    cache = manager.get_cache(cache_name) if cache_name else manager.get_default_cache()
    return cache.delete(key)


# 装饰器

def cached(ttl: Optional[int] = None, cache_name: Optional[str] = None, key_func: Optional[Callable] = None):
    """
    缓存函数结果的装饰器

    Args:
        ttl: TTL（秒）
        cache_name: 缓存名称
        key_func: 自定义key生成函数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # 生成缓存key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名+参数hash
                key_data = f"{func.__name__}:{args}:{kwargs}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # 尝试从缓存获取
            result = cache_get(cache_key, cache_name)

            if result is not None:
                return result

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            cache_set(cache_key, result, ttl, cache_name)

            return result

        return wrapper
    return decorator
