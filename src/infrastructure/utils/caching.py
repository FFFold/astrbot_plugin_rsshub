"""缓存工具模块

提供基于内存的缓存装饰器，支持 TTL 过期和条件缓存。

功能:
    - caching: 缓存方法返回值（类似 Spring @Cacheable）
    - cacheput: 强制更新缓存（类似 Spring @CachePut）
    - cacheevict: 清除缓存条目（类似 Spring @CacheEvict）

Examples:
    >>> @caching("feed_meta", key="#feed_id", ttl=300)
    ... async def fetch_feed_meta(self, feed_id: int) -> dict:
    ...     return await expensive_query(feed_id)

    >>> @cacheput("feed_meta", key="#feed_id")
    ... async def update_feed_meta(self, feed_id: int, data: dict) -> dict:
    ...     return data

    >>> @cacheevict("feed_meta", key="#feed_id")
    ... async def delete_feed(self, feed_id: int) -> None:
    ...     pass
"""

from __future__ import annotations

import abc
import asyncio
import functools
import inspect
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

from .expression_parser import CompiledExpression, ExpressionParser

F = TypeVar("F", bound=Callable[..., Any])


class BaseCache(abc.ABC):
    """缓存管理器抽象基类

    定义统一的缓存接口。

    所有方法均为线程/协程安全，由具体实现保证。
    """

    @abc.abstractmethod
    def get(self, cache_name: str, key: str) -> Any:
        """获取缓存值

        Args:
            cache_name: 缓存区域名称
            key: 缓存键

        Returns:
            缓存值，不存在或已过期时返回 None
        """

    @abc.abstractmethod
    def set(
        self,
        cache_name: str,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """设置缓存值

        Args:
            cache_name: 缓存区域名称
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 表示永不过期
        """

    @abc.abstractmethod
    def delete(self, cache_name: str, key: str) -> bool:
        """删除缓存条目

        Returns:
            是否成功删除
        """

    @abc.abstractmethod
    def clear(self, cache_name: str) -> int:
        """清空指定缓存区域

        Returns:
            被清除的条目数量
        """


class _CacheEntry:
    """缓存条目"""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float | None):
        self.value = value
        self.expires_at = time.time() + ttl if ttl else None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MemoryCache(BaseCache):
    """内存缓存管理器

    基于字典的内存缓存实现，支持按名称隔离的多个缓存区域和 TTL 过期。
    适合单实例部署场景，不支持分布式缓存。
    """

    def __init__(self):
        self._stores: dict[str, dict[str, _CacheEntry]] = defaultdict(dict)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_interval = 300.0  # 5分钟清理一次
        self._last_cleanup = time.time()

    def get(self, cache_name: str, key: str) -> Any:
        """获取缓存值"""
        store = self._stores.get(cache_name)
        if store is None:
            return None

        entry = store.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            del store[key]
            return None

        return entry.value

    def set(
        self,
        cache_name: str,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """设置缓存值"""
        self._stores[cache_name][key] = _CacheEntry(value, ttl)

    def delete(self, cache_name: str, key: str) -> bool:
        """删除缓存条目"""
        store = self._stores.get(cache_name)
        if store is None:
            return False
        if key in store:
            del store[key]
            return True
        return False

    def clear(self, cache_name: str) -> int:
        """清空指定缓存区域"""
        store = self._stores.get(cache_name)
        if store is None:
            return 0
        count = len(store)
        store.clear()
        return count

    def get_lock(self, cache_name: str) -> asyncio.Lock:
        """获取缓存区域的锁"""
        return self._locks[cache_name]

    async def cleanup_expired(self) -> None:
        """清理所有过期的缓存条目"""
        now = time.time()
        for store in self._stores.values():
            expired_keys = [
                k for k, entry in store.items()
                if entry.expires_at and now > entry.expires_at
            ]
            for k in expired_keys:
                del store[k]

    async def start_cleanup_task(self) -> None:
        """启动后台清理任务"""
        if self._cleanup_task is not None:
            return

        async def _cleanup_loop() -> None:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_expired()

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """停止后台清理任务"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None


def _validate_key(key: str) -> None:
    """验证缓存键表达式有效"""
    if not key or not key.strip():
        raise ValueError("Cache key expression cannot be empty")


def _build_cache_key(
    key_expr: str | CompiledExpression,
    args: tuple,
    kwargs: dict,
    param_names: list[str],
) -> str:
    """构建缓存键"""
    if isinstance(key_expr, CompiledExpression):
        raw = key_expr.evaluate(args, kwargs, param_names)
    else:
        raw = ExpressionParser.parse(key_expr, args, kwargs, param_names)
    return str(raw)


# 全局缓存实例
_cache_instance: BaseCache | None = None


def get_memory_cache() -> BaseCache:
    """获取全局缓存实例

    默认返回 MemoryCache，后续可通过 set_cache_backend() 切换为其他实现。
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MemoryCache()
    return _cache_instance


def set_cache_backend(backend: BaseCache) -> None:
    """设置全局缓存后端

    用于切换为 RedisCache、DiskCache 等其他实现。

    Args:
        backend: 缓存后端实例
    """
    global _cache_instance
    _cache_instance = backend


def caching(
    cache_name: str,
    *,
    key: str,
    ttl: float | None = None,
    condition: str | None = None,
) -> Callable[[F], F]:
    """缓存装饰器（类似 Spring @Cacheable）

    如果缓存中存在值，直接返回缓存值；否则执行函数并缓存结果。

    Args:
        cache_name: 缓存区域名称
        key: 缓存键表达式（SpEL），默认使用函数名+参数
        ttl: 过期时间（秒），None 表示永不过期
        condition: 条件表达式（SpEL），为真时才缓存

    Examples:
        >>> @caching("feed_meta", key="#feed_id", ttl=300)
        ... async def fetch_feed(self, feed_id: int) -> dict:
        ...     return await expensive_query(feed_id)

        >>> @caching("translations", key="#text+#target_lang", ttl=3600)
        ... async def translate(self, text: str, target_lang: str) -> str:
        ...     return await translator.translate(text, target_lang)
    """
    _validate_key(key)
    cache = get_memory_cache()
    compiled_key = CompiledExpression(key)
    compiled_condition = CompiledExpression(condition) if condition else None

    def decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        def _eval_condition(args: tuple, kwargs: dict) -> bool:
            if compiled_condition is None:
                return True
            cond_result = compiled_condition.evaluate(args, kwargs, param_names)
            return bool(cond_result)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = _build_cache_key(
                compiled_key, args, kwargs, param_names
            )

            # 检查缓存
            cached = cache.get(cache_name, cache_key)
            if cached is not None:
                return cached

            # 执行函数
            result = await func(*args, **kwargs)

            if _eval_condition(args, kwargs):
                cache.set(cache_name, cache_key, result, ttl)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = _build_cache_key(
                compiled_key, args, kwargs, param_names
            )

            cached = cache.get(cache_name, cache_key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)

            if _eval_condition(args, kwargs):
                cache.set(cache_name, cache_key, result, ttl)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def cacheput(
    cache_name: str,
    *,
    key: str,
    ttl: float | None = None,
    condition: str | None = None,
) -> Callable[[F], F]:
    """缓存更新装饰器（类似 Spring @CachePut）

    始终执行函数，并将结果写入缓存。

    Args:
        cache_name: 缓存区域名称
        key: 缓存键表达式（SpEL）
        ttl: 过期时间（秒）
        condition: 条件表达式（SpEL）

    Examples:
        >>> @cacheput("feed_meta", key="#feed_id")
        ... async def update_feed(self, feed_id: int, data: dict) -> dict:
        ...     await db.update(feed_id, data)
        ...     return data
    """
    _validate_key(key)
    cache = get_memory_cache()
    compiled_key = CompiledExpression(key)
    compiled_condition = CompiledExpression(condition) if condition else None

    def decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        def _eval_condition(args: tuple, kwargs: dict) -> bool:
            if compiled_condition is None:
                return True
            cond_result = compiled_condition.evaluate(args, kwargs, param_names)
            return bool(cond_result)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            if _eval_condition(args, kwargs):
                cache_key = _build_cache_key(
                    compiled_key, args, kwargs, param_names
                )
                cache.set(cache_name, cache_key, result, ttl)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if _eval_condition(args, kwargs):
                cache_key = _build_cache_key(
                    compiled_key, args, kwargs, param_names
                )
                cache.set(cache_name, cache_key, result, ttl)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def cacheevict(
    cache_name: str,
    *,
    key: str | None = None,
    all_entries: bool = False,
    before_invocation: bool = False,
) -> Callable[[F], F]:
    """缓存清除装饰器（类似 Spring @CacheEvict）

    清除指定缓存条目或整个缓存区域。

    Args:
        cache_name: 缓存区域名称
        key: 缓存键表达式（SpEL），all_entries=False 时必须提供
        all_entries: 是否清除整个缓存区域
        before_invocation: 是否在方法执行前清除

    Examples:
        >>> @cacheevict("feed_meta", key="#feed_id")
        ... async def delete_feed(self, feed_id: int) -> None:
        ...     pass

        >>> @cacheevict("translations", all_entries=True)
        ... async def clear_translations(self) -> None:
        ...     pass
    """
    if not all_entries:
        _validate_key(key)
    cache = get_memory_cache()
    compiled_key = CompiledExpression(key) if key else None

    def decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        def _do_evict(args: tuple, kwargs: dict) -> None:
            if all_entries:
                cache.clear(cache_name)
            elif compiled_key is not None:
                cache_key = _build_cache_key(
                    compiled_key, args, kwargs, param_names
                )
                cache.delete(cache_name, cache_key)
            else:
                raise ValueError(
                    "cacheevict requires either 'key' or 'all_entries=True'"
                )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if before_invocation:
                _do_evict(args, kwargs)
            result = await func(*args, **kwargs)
            if not before_invocation:
                _do_evict(args, kwargs)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if before_invocation:
                _do_evict(args, kwargs)
            result = func(*args, **kwargs)
            if not before_invocation:
                _do_evict(args, kwargs)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "BaseCache",
    "MemoryCache",
    "get_memory_cache",
    "set_cache_backend",
    "caching",
    "cacheput",
    "cacheevict",
]
