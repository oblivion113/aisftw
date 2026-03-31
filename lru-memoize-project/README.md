# LRU Memoize Project

This project builds two cache decorators, validates them against `functools.lru_cache`, benchmarks their overhead, and records brief CPython source notes.

## Core Logic

- [src/naive_memoize.py](/home/yolanda/code/demo/lru-memoize-project/src/naive_memoize.py) implements unbounded memoization with a plain `dict`.
- [src/lru_memoize.py](/home/yolanda/code/demo/lru-memoize-project/src/lru_memoize.py) implements bounded or unbounded LRU caching with `OrderedDict`.
- [src/workloads.py](/home/yolanda/code/demo/lru-memoize-project/src/workloads.py) defines workload factories such as `make_fib()` so recursive calls go through the decorated function.

Both decorators expose:

- `cache_info()`
- `cache_clear()`

The project versions intentionally stay simple:

- positional arguments only
- arguments must be hashable
- no keyword-argument handling
- no thread-safety layer

## Repository Layout

```text
src/                decorator implementations and workload factories
tests/              correctness checks and stdlib comparison
experiments/        benchmark scripts
results/            benchmark CSV outputs and figures
cpython_analysis/   notes about `functools.lru_cache` internals
report/             project write-up
```

More specifically:

- [tests/test_naive_memoize.py](/home/yolanda/code/demo/lru-memoize-project/tests/test_naive_memoize.py) checks the unbounded memoizer.
- [tests/test_lru_memoize.py](/home/yolanda/code/demo/lru-memoize-project/tests/test_lru_memoize.py) checks eviction and access-order behavior.
- [tests/test_against_stdlib.py](/home/yolanda/code/demo/lru-memoize-project/tests/test_against_stdlib.py) compares values and `cache_info()` against `functools.lru_cache`.
- [experiments/bench_recursive.py](/home/yolanda/code/demo/lru-memoize-project/experiments/bench_recursive.py), [experiments/bench_cache_pressure.py](/home/yolanda/code/demo/lru-memoize-project/experiments/bench_cache_pressure.py), and [experiments/bench_overhead.py](/home/yolanda/code/demo/lru-memoize-project/experiments/bench_overhead.py) produce the benchmark data in `results/`.

## CPython Context

- [cpython_analysis/notes.md](/home/yolanda/code/demo/lru-memoize-project/cpython_analysis/notes.md) summarizes how stdlib `lru_cache` splits work between `functools.py` and the `_functools` C accelerator.
- [cpython_analysis/_functoolsmodule.c](/home/yolanda/code/demo/lru-memoize-project/cpython_analysis/_functoolsmodule.c) is a local source copy for reference.
