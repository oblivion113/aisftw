"""Generate plots from the raw CSV files produced by the benchmarks.

Each plotting function reads one benchmark output file and turns it into a
summary figure:

- ``plot_recursive()`` shows Fibonacci timing versus ``n``
- ``plot_cache_pressure()`` shows hit rate under different cache sizes
- ``plot_overhead()`` shows per-call warm-cache overhead
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of row dictionaries."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_recursive() -> None:
    """Plot mean recursive timing with standard-deviation bands."""
    rows = read_csv(RESULTS_DIR / "recursive.csv")
    grouped: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["variant"]][int(row["n"])].append(int(row["time_ns"]))

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(9, 5))
    for variant, by_n in grouped.items():
        ns = sorted(by_n)
        means = np.array([statistics.mean(by_n[n]) for n in ns], dtype=float)
        stds = np.array([statistics.stdev(by_n[n]) if len(by_n[n]) > 1 else 0.0 for n in ns], dtype=float)
        ax.plot(ns, means, marker="o", label=variant)
        ax.fill_between(ns, means - stds, means + stds, alpha=0.15)

    ax.set_yscale("log")
    ax.set_xlabel("n")
    ax.set_ylabel("Mean time (ns, log scale)")
    ax.set_title("Recursive Fibonacci Timing")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "recursive_timing.png", dpi=200)
    plt.close(fig)


def plot_cache_pressure() -> None:
    """Plot hit rate for each cache size and key-space size."""
    rows = read_csv(RESULTS_DIR / "cache_pressure.csv")
    ks = sorted({int(row["K"]) for row in rows})
    maxsizes = sorted({int(row["maxsize"]) for row in rows})
    variants = ["lru_memoize", "functools.lru_cache"]
    width = 0.35

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, len(ks), figsize=(14, 4), sharey=True)
    if len(ks) == 1:
        axes = [axes]

    for ax, k in zip(axes, ks):
        x = np.arange(len(maxsizes))
        for idx, variant in enumerate(variants):
            hit_rates = []
            for maxsize in maxsizes:
                row = next(
                    item for item in rows if item["variant"] == variant and int(item["K"]) == k and int(item["maxsize"]) == maxsize
                )
                hit_rates.append(float(row["hit_rate"]))
            ax.bar(x + (idx - 0.5) * width, hit_rates, width=width, label=variant)

        ax.set_title(f"K={k}")
        ax.set_xticks(x)
        ax.set_xticklabels([str(value) for value in maxsizes], rotation=45)
        ax.set_xlabel("maxsize")

    axes[0].set_ylabel("Hit rate")
    axes[0].set_ylim(0, 1)
    axes[0].legend()
    fig.suptitle("Cache Pressure Hit Rate")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "cache_pressure_hitrate.png", dpi=200)
    plt.close(fig)


def plot_overhead() -> None:
    """Plot mean per-call overhead with error bars for each variant."""
    rows = read_csv(RESULTS_DIR / "overhead.csv")
    variants = []
    means = []
    stds = []

    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["variant"]].append(float(row["per_call_ns"]))

    for variant, samples in grouped.items():
        variants.append(variant)
        means.append(statistics.mean(samples))
        stds.append(statistics.stdev(samples) if len(samples) > 1 else 0.0)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(variants, means, yerr=stds, capsize=4)
    ax.set_ylabel("Per-call overhead (ns)")
    ax.set_title("Cache Hit Overhead")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "overhead_per_call.png", dpi=200)
    plt.close(fig)


def main() -> None:
    """Generate all figures into ``results/figures``."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plot_recursive()
    plot_cache_pressure()
    plot_overhead()


if __name__ == "__main__":
    main()
