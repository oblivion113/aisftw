"""Naive unbounded memoization decorator."""

from __future__ import annotations

from collections import namedtuple
from functools import wraps
from typing import Any, Callable


CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


def memoize(func: Callable[..., Any]) -> Callable[..., Any]:
    """Memoize a function using an unbounded dictionary keyed by ``args``.

    This project intentionally keeps the implementation simple:
    it only supports hashable positional arguments and ignores keyword
    arguments. Unhashable arguments will naturally raise ``TypeError`` when
    used as dictionary keys.
    """

    cache: dict[tuple[Any, ...], Any] = {}
    hits = 0
    misses = 0

    @wraps(func)
    def wrapper(*args: Any) -> Any:
        nonlocal hits, misses
        if args in cache:
            hits += 1
            return cache[args]

        misses += 1
        result = func(*args)
        cache[args] = result
        return result

    def cache_info() -> CacheInfo:
        return CacheInfo(hits=hits, misses=misses, maxsize=None, currsize=len(cache))

    def cache_clear() -> None:
        nonlocal hits, misses
        cache.clear()
        hits = 0
        misses = 0

    wrapper.cache_info = cache_info  # type: ignore[attr-defined]
    wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
    return wrapper
