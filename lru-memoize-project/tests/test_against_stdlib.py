"""Cross-validation against functools.lru_cache."""

from __future__ import annotations

from functools import lru_cache

from src.lru_memoize import lru_memoize
from src.workloads import make_fib


def test_matches_stdlib_cache_info_and_values() -> None:
    for maxsize in (32, 64, 128, None):
        ours = make_fib(lru_memoize(maxsize=maxsize))
        theirs = make_fib(lru_cache(maxsize=maxsize))

        ours_values = [ours(n) for n in range(50)]
        theirs_values = [theirs(n) for n in range(50)]

        assert ours_values == theirs_values
        assert ours.cache_info() == theirs.cache_info()
