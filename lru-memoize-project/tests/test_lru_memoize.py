"""Tests for the LRU memoization decorator."""

from __future__ import annotations

from src.lru_memoize import lru_memoize
from src.workloads import make_fib


def test_fibonacci_correctness() -> None:
    fib = make_fib(lru_memoize())

    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(10) == 55
    assert fib(30) == 832040


def test_cache_counters() -> None:
    fib = make_fib(lru_memoize(maxsize=None))

    fib(5)
    info = fib.cache_info()

    assert info.hits > 0
    assert info.misses == 6
    assert info.currsize == 6
    assert info.maxsize is None


def test_cache_clear_resets_state() -> None:
    fib = make_fib(lru_memoize(maxsize=None))

    fib(5)
    fib.cache_clear()

    cleared = fib.cache_info()
    assert cleared.currsize == 0
    assert cleared.hits == 0
    assert cleared.misses == 0

    fib(5)
    assert fib.cache_info().misses == 6


def test_multiple_functions_have_independent_caches() -> None:
    @lru_memoize(maxsize=8)
    def square(x: int) -> int:
        return x * x

    @lru_memoize(maxsize=8)
    def cube(x: int) -> int:
        return x * x * x

    square(3)
    square(3)
    cube(3)

    assert square.cache_info().hits == 1
    assert square.cache_info().misses == 1
    assert cube.cache_info().hits == 0
    assert cube.cache_info().misses == 1


def test_unhashable_arguments_raise_type_error() -> None:
    @lru_memoize()
    def echo(value: list[int]) -> list[int]:
        return value

    try:
        echo([1, 2, 3])
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError for unhashable arguments")


def test_eviction_correctness() -> None:
    @lru_memoize(maxsize=3)
    def identity(x: int) -> int:
        return x

    identity(1)
    identity(2)
    identity(3)
    identity(4)

    before = identity.cache_info()
    identity(1)
    after = identity.cache_info()

    assert before.currsize == 3
    assert after.currsize == 3
    assert after.misses == before.misses + 1


def test_access_order_updates_on_hit() -> None:
    @lru_memoize(maxsize=3)
    def identity(x: int) -> int:
        return x

    identity(1)
    identity(2)
    identity(3)
    identity(1)
    before = identity.cache_info()

    identity(4)
    middle = identity.cache_info()
    identity(2)
    after = identity.cache_info()

    assert middle.currsize == 3
    assert after.misses == before.misses + 2


def test_maxsize_one_only_keeps_most_recent_entry() -> None:
    @lru_memoize(maxsize=1)
    def identity(x: int) -> int:
        return x

    identity(1)
    identity(2)
    before = identity.cache_info()
    identity(1)
    after = identity.cache_info()

    assert before.currsize == 1
    assert after.currsize == 1
    assert after.misses == before.misses + 1


def test_maxsize_none_never_evicts() -> None:
    @lru_memoize(maxsize=None)
    def identity(x: int) -> int:
        return x

    for value in range(10):
        identity(value)

    assert identity.cache_info().currsize == 10
