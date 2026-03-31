"""Tests for the naive memoization decorator."""

from __future__ import annotations

from src.naive_memoize import memoize
from src.workloads import make_fib


def test_fibonacci_correctness() -> None:
    fib = make_fib(memoize)

    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(10) == 55
    assert fib(30) == 832040


def test_cache_counters() -> None:
    fib = make_fib(memoize)

    fib(5)
    info = fib.cache_info()

    assert info.hits > 0
    assert info.misses == 6
    assert info.currsize == 6
    assert info.maxsize is None


def test_cache_clear_resets_state() -> None:
    fib = make_fib(memoize)

    fib(5)
    fib.cache_clear()

    cleared = fib.cache_info()
    assert cleared.currsize == 0
    assert cleared.hits == 0
    assert cleared.misses == 0

    fib(5)
    info = fib.cache_info()
    assert info.misses == 6


def test_multiple_functions_have_independent_caches() -> None:
    @memoize
    def square(x: int) -> int:
        return x * x

    @memoize
    def cube(x: int) -> int:
        return x * x * x

    assert square(3) == 9
    assert square(3) == 9
    assert cube(3) == 27

    square_info = square.cache_info()
    cube_info = cube.cache_info()
    assert square_info.hits == 1
    assert square_info.misses == 1
    assert cube_info.hits == 0
    assert cube_info.misses == 1


def test_unhashable_arguments_raise_type_error() -> None:
    @memoize
    def echo(value: list[int]) -> list[int]:
        return value

    try:
        echo([1, 2, 3])
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError for unhashable arguments")
