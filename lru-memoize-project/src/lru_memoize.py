"""LRU memoization decorator built on ``OrderedDict``."""

from __future__ import annotations

from collections import OrderedDict, namedtuple
from functools import wraps
from typing import Any, Callable


CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


def lru_memoize(maxsize: int | None = 128) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator implementing LRU caching with ``OrderedDict``.

    The implementation intentionally mirrors the project guide:
    positional hashable arguments only, no keyword arguments, and no thread
    safety. ``maxsize=None`` disables eviction and behaves as an unbounded
    cache.
    """

    if maxsize is not None and maxsize < 0:
        raise ValueError("maxsize must be non-negative or None")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        hits = 0
        misses = 0

        @wraps(func)
        def wrapper(*args: Any) -> Any:
            nonlocal hits, misses
            if args in cache:
                hits += 1
                cache.move_to_end(args)
                return cache[args]

            misses += 1
            result = func(*args)

            if maxsize == 0:
                return result

            cache[args] = result
            cache.move_to_end(args)
            if maxsize is not None and len(cache) > maxsize:
                cache.popitem(last=False)
            return result

        def cache_info() -> CacheInfo:
            return CacheInfo(hits=hits, misses=misses, maxsize=maxsize, currsize=len(cache))

        def cache_clear() -> None:
            nonlocal hits, misses
            cache.clear()
            hits = 0
            misses = 0

        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
