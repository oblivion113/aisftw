"""Measure the steady-state cost of a warm cache hit.

This benchmark uses the trivial ``identity`` function so almost all measured
time comes from the wrapper itself rather than from useful computation.

The benchmark warms the cache once, then calls the wrapped function many times
with the same argument. That makes nearly every call a cache hit. Comparing the
variants shows the overhead added by:

- no decorator at all
- our plain dict-based memoizer
- our ``OrderedDict``-based LRU cache
- ``functools.lru_cache``
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
from src.workloads import identity

RESULTS_PATH = ROOT / "results" / "overhead.csv"
CALLS = 1_000_000
REPETITIONS = 20


def run_trial(func: Callable[[int], int]) -> int:
    """Time a long run of repeated calls to the same warmed function."""
    start = time.perf_counter_ns()
    for _ in range(CALLS):
        func(0)
    return time.perf_counter_ns() - start


def benchmark_variant(name: str, func_factory: Callable[[], Callable[[int], int]]) -> list[dict[str, int | float | str]]:
    """Collect repeated warm-cache timing samples for one implementation."""
    rows: list[dict[str, int | float | str]] = []
    timings = []

    for trial in range(REPETITIONS):
        func = func_factory()
        if hasattr(func, "cache_clear"):
            func.cache_clear()  # type: ignore[attr-defined]
            func(0)
        elapsed = run_trial(func)
        per_call = elapsed / CALLS
        timings.append(per_call)
        rows.append(
            {
                "variant": name,
                "trial": trial,
                "total_time_ns": elapsed,
                "calls": CALLS,
                "per_call_ns": per_call,
            }
        )

    mean_ns = statistics.mean(timings)
    std_ns = statistics.stdev(timings) if len(timings) > 1 else 0.0
    print(f"{name:26} mean={mean_ns:10.2f} ns/call std={std_ns:10.2f}")
    return rows


def main() -> None:
    """Run the overhead benchmark and write per-trial results to CSV."""
    rows = []
    rows.extend(benchmark_variant("bare", lambda: identity))
    rows.extend(benchmark_variant("memoize", lambda: memoize(identity)))
    rows.extend(benchmark_variant("lru_memoize(128)", lambda: lru_memoize(maxsize=128)(identity)))
    rows.extend(benchmark_variant("functools.lru_cache(128)", lambda: lru_cache(maxsize=128)(identity)))

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "trial", "total_time_ns", "calls", "per_call_ns"],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
