"""Benchmark hit rate and runtime when the cache is smaller than the key space.

This benchmark is meant to answer a different question from the recursive and
pure-overhead benchmarks:

- not "how fast is memoized Fibonacci?"
- not "what is the cost of a single warm cache hit?"
- but "how well does the LRU policy behave when many distinct keys compete for
  a limited cache?"

The script replays the same fixed access trace for both implementations:

- ``K`` is the number of distinct keys that may appear
- ``maxsize`` is the cache capacity
- ``CALLS`` is the length of the access trace

The trace is generated from a Zipf-like distribution, which means some keys are
requested much more often than others. That creates temporal locality and makes
LRU meaningful: a good LRU cache should keep hot keys and evict colder ones.

For each ``(maxsize, K)`` pair, the benchmark:

1. wraps ``square`` with the chosen cache decorator
2. replays the same sequence of integer inputs
3. reads ``cache_info()`` to get hits and misses
4. records hit rate and total runtime

Using the exact same input sequence for both implementations is important.
Otherwise a hit-rate difference could come from different random samples rather
than from the cache behavior itself.
"""

from __future__ import annotations

import csv
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.lru_memoize import lru_memoize

RESULTS_PATH = ROOT / "results" / "cache_pressure.csv"
MAXSIZES = [8, 16, 32, 64, 128, 256]
KS = [64, 256, 1024]
CALLS = 100_000
RNG = np.random.default_rng(20260331)
SEQUENCES = {k: (RNG.zipf(a=1.5, size=CALLS) % k).astype(int) for k in KS}


def square(x: int) -> int:
    """Small pure function used to isolate cache behavior from work cost."""
    return x * x


def run_variant(
    name: str, decorator_factory: Callable[[int], Callable[[Callable[[int], int]], Callable[[int], int]]]
) -> list[dict[str, int | float | str]]:
    """Run one cache implementation across all ``maxsize`` and ``K`` settings.

    ``K`` controls how many unique keys compete for space in the cache. When
    ``K`` is much larger than ``maxsize``, the cache is under heavy pressure
    and must evict often. When ``K`` is closer to ``maxsize``, the cache can
    retain more of the working set and the hit rate should rise.
    """
    rows: list[dict[str, int | float | str]] = []

    for maxsize in MAXSIZES:
        for k in KS:
            wrapped = decorator_factory(maxsize)(square)
            sequence = SEQUENCES[k]

            start = time.perf_counter_ns()
            for value in sequence:
                wrapped(int(value))
            elapsed = time.perf_counter_ns() - start

            info = wrapped.cache_info()
            hit_rate = info.hits / (info.hits + info.misses)
            print(
                f"{name:26} maxsize={maxsize:3d} K={k:4d} "
                f"hits={info.hits:6d} misses={info.misses:6d} "
                f"hit_rate={hit_rate:.4f} total={elapsed} ns"
            )
            rows.append(
                {
                    "variant": name,
                    "maxsize": maxsize,
                    "K": k,
                    "hits": info.hits,
                    "misses": info.misses,
                    "hit_rate": hit_rate,
                    "total_time_ns": elapsed,
                }
            )
    return rows


def main() -> None:
    """Benchmark our LRU cache against ``functools.lru_cache`` and save CSV."""
    rows = []
    rows.extend(run_variant("lru_memoize", lambda maxsize: lru_memoize(maxsize=maxsize)))
    rows.extend(run_variant("functools.lru_cache", lambda maxsize: lru_cache(maxsize=maxsize)))

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "maxsize", "K", "hits", "misses", "hit_rate", "total_time_ns"],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
