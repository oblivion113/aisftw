# CPython `lru_cache` Notes

## Source Files

Use Python metadata to locate the Python-side source:

```python
import functools
print(functools.__file__)
```

In this environment that points to:

```text
/home/yolanda/miniconda3/lib/python3.13/functools.py
```

You can confirm the accelerator module at runtime with:

```python
import _functools
print(_functools)
print(_functools._lru_cache_wrapper)
```

That tells you the runtime is using the built-in `_functools` module. The C source for that module is not part of the installed Conda runtime; in a CPython source checkout it lives at:

```text
Modules/_functoolsmodule.c
```

## Execution Flow

When you write:

```python
from functools import lru_cache

@lru_cache(maxsize=4)
def f(x):
    return x * 2
```

the flow is:

1. CPython imports and executes `functools.py`.
2. `lru_cache()` runs as normal Python code.
3. `lru_cache()` creates a wrapper by calling `_lru_cache_wrapper(...)`.
4. In CPython, `_lru_cache_wrapper` is usually provided by the C accelerator `_functools`.
5. The decorated name `f` now refers to the cache wrapper, not directly to the original function.
6. On each call, the wrapper checks the cache first and only calls the original Python function on a miss.

So `lru_cache` is a Python API around a usually C-backed cache wrapper.

## What `functools.py` Does

The stdlib file `functools.py` contains:

- the public `lru_cache()` decorator
- a pure-Python `_lru_cache_wrapper` fallback
- helper methods such as `cache_info()` and `cache_clear()`

The pure-Python implementation has three modes:

- `maxsize == 0`: no caching
- `maxsize is None`: unbounded cache
- otherwise: bounded LRU cache

For bounded LRU mode, the Python fallback uses:

- a dict for key lookup
- a circular doubly linked list for recency order
- an `RLock` for thread safety

Each linked-list node stores:

```text
[PREV, NEXT, KEY, RESULT]
```

The root node points to itself when the cache is empty:

```text
empty:
    root
   /    \
 root  root

one entry:
    root <-> A <-> root

three entries:
    root <-> A <-> B <-> C <-> root
```

This design gives O(1) lookup, promotion on hit, and eviction.

## What the C Code Does

`Modules/_functoolsmodule.c` implements the accelerated `_lru_cache_wrapper`.

Its job is the same as the Python fallback:

- build or receive a cache key
- look up the key
- return cached results on hits
- call the original function on misses
- store results
- maintain LRU ordering
- expose cache stats and cache clearing

The difference is implementation level:

- the Python fallback uses Python objects and Python lists
- the C accelerator uses C structs and CPython object-management code

That is why the C path is faster but harder to read.

## Why CPython Does Not Use `OrderedDict`

This project uses `OrderedDict` because it is simple and readable.

CPython instead uses a dict plus a custom linked structure so it can:

- avoid an extra abstraction layer
- control pointer updates directly
- minimize overhead on hot cache operations

## Thread Safety

In the pure-Python fallback, `RLock` protects the linked-list updates.

In the C accelerator, synchronization is handled at the interpreter/runtime level rather than by copying the exact Python locking structure. The important beginner takeaway is that CPython's stdlib version is designed for production use, while this project intentionally keeps the teaching implementation simple.

## Differences From This Project

Compared with [src/lru_memoize.py](/home/yolanda/code/demo/lru-memoize-project/src/lru_memoize.py):

- CPython uses a custom linked structure, not `OrderedDict`
- CPython supports more cases, including keyword arguments and typed caching
- CPython's hot path is usually implemented in C
- this project favors readability over completeness and speed
