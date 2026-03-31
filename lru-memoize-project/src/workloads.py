"""Workloads for tests and benchmarks."""

from __future__ import annotations

from typing import Callable, TypeVar


F = TypeVar("F", bound=Callable[..., int])


def make_fib(decorator: Callable[[F], F]) -> F:
    """Build a recursively memoizable Fibonacci function.

    The recursive calls resolve through the decorated ``fib`` name inside this
    closure, so rebinding is explicit and correct for experiments.
    """

    @decorator
    def fib(n: int) -> int:
        if n < 2:
            return n
        return fib(n - 1) + fib(n - 2)

    return fib


def make_grid_paths(decorator: Callable[[F], F]) -> F:
    """Build a recursively memoizable grid-path counter."""

    @decorator
    def grid_paths(m: int, n: int) -> int:
        if m == 0 or n == 0:
            return 1
        return grid_paths(m - 1, n) + grid_paths(m, n - 1)

    return grid_paths


def expensive_pure(x: int) -> int:
    """A deliberately slow pure function for overhead benchmarks."""

    total = 0
    for i in range(100):
        total += i * x
    return total


def identity(x: int) -> int:
    """Trivially cheap function for measuring cache-hit overhead."""

    return x
