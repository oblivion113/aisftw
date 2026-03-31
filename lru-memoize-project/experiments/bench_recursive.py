"""Benchmark recursive Fibonacci under several memoization strategies.

This experiment measures end-to-end runtime for ``fib(n)`` at increasing input
sizes. The goal is to compare:

- our unbounded memoizer
- our ``OrderedDict``-based LRU cache
- CPython's ``functools.lru_cache``

Each trial creates a fresh decorated Fibonacci function, clears its cache, runs
``fib(n)``, and records the elapsed time. Rebuilding the function each trial
avoids carrying cache state from one trial or one ``n`` value into the next.
"""

from __future__ import annotations

import csv
import statistics
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.lru_memoize import lru_memoize
from src.naive_memoize import memoize
from src.workloads import make_fib

RESULTS_PATH = ROOT / "results" / "recursive.csv"
REPETITIONS = 10
NS = [10, 15, 20, 25, 30, 35, 40]


def benchmark_variant(name: str, factory: Callable[[], Callable[[int], int]]) -> list[dict[str, int | str]]:
    """Measure one decorator strategy across the configured Fibonacci inputs."""
    rows: list[dict[str, int | str]] = []
    for n in NS:
        timings = []
        for trial in range(REPETITIONS):
            fib = factory()
            fib.cache_clear()
            start = time.perf_counter_ns()
            fib(n)
            elapsed = time.perf_counter_ns() - start
            timings.append(elapsed)
            rows.append({"variant": name, "n": n, "trial": trial, "time_ns": elapsed})

        mean_ns = statistics.mean(timings)
        std_ns = statistics.stdev(timings) if len(timings) > 1 else 0.0
        print(f"{name:28} n={n:2d} mean={mean_ns:>12.1f} ns std={std_ns:>12.1f} ns")
    return rows


def main() -> None:
    """Run all recursive benchmarks and write raw timings to CSV."""
    variants: list[tuple[str, Callable[[], Callable[[int], int]]]] = [
        ("memoize", lambda: make_fib(memoize)),
        ("lru_memoize(None)", lambda: make_fib(lru_memoize(maxsize=None))),
        ("lru_memoize(128)", lambda: make_fib(lru_memoize(maxsize=128))),
        ("functools.lru_cache(None)", lambda: make_fib(lru_cache(maxsize=None))),
        ("functools.lru_cache(128)", lambda: make_fib(lru_cache(maxsize=128))),
    ]

    rows: list[dict[str, int | str]] = []
    for name, factory in variants:
        rows.extend(benchmark_variant(name, factory))

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["variant", "n", "trial", "time_ns"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
