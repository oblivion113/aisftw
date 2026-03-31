# LRU Cache Internal Execution Flow

This document traces the actual code execution logic inside the two CPython source
files that implement `functools.lru_cache`, and compares them with this project's
`src/lru_memoize.py`. It does not cover how to locate the files; it covers what
the code inside those files does, function by function.

---

## The Two Files and How They Relate

**`Lib/functools.py`** defines:
- the public decorator `lru_cache()` — a decorator factory
- a pure-Python fallback `_lru_cache_wrapper()` — the full algorithm in Python

**`Modules/_functoolsmodule.c`** defines:
- a C implementation of `_lru_cache_wrapper` as a Python type (`lru_cache_object`)
- the same algorithm in C, with dedicated structs and direct reference counting

The last lines of `functools.py` are:

```python
try:
    from _functools import _lru_cache_wrapper   # (functools.py line 717)
except ImportError:
    pass
```

This replaces the Python `_lru_cache_wrapper` with the C one whenever the C
extension is available (which it always is in a standard CPython build). The
public `lru_cache()` factory in `functools.py` still runs in Python; it just
hands off the wrapper object construction to the C type.

---

## Part 1 — `functools.py`: the Python side

### `lru_cache()` — decorator factory (lines 553–598)

This function handles the three legal calling styles:

```python
@lru_cache            # bare, no parens
@lru_cache(maxsize=64)
@lru_cache(maxsize=None, typed=True)
```

The logic that makes the bare-decorator style work is:

```python
elif callable(maxsize) and isinstance(typed, bool):
    # user passed the function directly as the first argument
    user_function, maxsize = maxsize, 128
    wrapper = _lru_cache_wrapper(user_function, maxsize, typed, _CacheInfo)
    ...
    return update_wrapper(wrapper, user_function)
```

When called with explicit arguments, it returns a `decorating_function` closure
that receives the real function and calls `_lru_cache_wrapper`. In both paths the
final step is `update_wrapper(wrapper, user_function)`, which copies `__name__`,
`__doc__`, `__module__`, etc. onto the wrapper and sets `wrapper.__wrapped__` to
the original function.

---

### `_lru_cache_wrapper()` — pure-Python fallback (lines 600–714)

This is the most instructive version because every data structure and pointer
operation is visible in Python.

#### Closure state created once per decorated function

```python
sentinel  = object()           # unique miss-signal; cheaper than None
make_key  = _make_key          # builds a hashable cache key from args/kwds
PREV, NEXT, KEY, RESULT = 0, 1, 2, 3   # index names for list nodes

cache     = {}                 # dict: key → link (the list node for that entry)
hits = misses = 0
full      = False              # True once len(cache) == maxsize
cache_get = cache.get          # avoids a global lookup on every call
cache_len = cache.__len__
lock      = RLock()            # protects all list mutations
root      = []
root[:] = [root, root, None, None]   # sentinel node points to itself
```

The circular doubly-linked list uses plain Python `list` objects as nodes.
`root` is the sentinel: it is always present and never holds real data. Its
`NEXT` pointer leads to the LRU (oldest) item; its `PREV` pointer leads to the
MRU (newest) item. An empty list looks like:

```
root.NEXT → root
root.PREV → root
```

After inserting A, B, C (A is oldest):

```
root.NEXT → A → B → C → root
root.PREV ─────────────── C
```

#### Branch 1: `maxsize == 0` — no caching

```python
def wrapper(*args, **kwds):
    nonlocal misses
    misses += 1
    result = user_function(*args, **kwds)
    return result
```

Every call is a miss. The function is always called. Cache is never touched.

#### Branch 2: `maxsize is None` — unbounded cache

```python
def wrapper(*args, **kwds):
    nonlocal hits, misses
    key = make_key(args, kwds, typed)
    result = cache_get(key, sentinel)   # O(1) dict lookup
    if result is not sentinel:
        hits += 1
        return result
    misses += 1
    result = user_function(*args, **kwds)
    cache[key] = result
    return result
```

No eviction, no list management. Just a dictionary. The sentinel is used instead
of `None` to correctly handle functions that return `None`.

#### Branch 3: bounded LRU — the main case

The wrapper is split into **two lock acquisitions** with the user function call
sitting between them (outside the lock), so the function itself doesn't block
other threads from reading the cache.

**First critical section — lookup:**

```python
key = make_key(args, kwds, typed)
with lock:
    link = cache_get(key)
    if link is not None:
        # --- cache hit ---
        link_prev, link_next, _key, result = link

        # Splice the link out of its current position
        link_prev[NEXT] = link_next
        link_next[PREV] = link_prev

        # Re-insert it at the MRU end (just before root)
        last = root[PREV]
        last[NEXT] = root[PREV] = link
        link[PREV] = last
        link[NEXT] = root

        hits += 1
        return result
    misses += 1
```

The six pointer assignments above are the core of the LRU move-to-front
operation. They do two things atomically (under the lock):
remove the node from wherever it is, then attach it as the newest node.

**User function call (lock released):**

```python
result = user_function(*args, **kwds)
```

**Second critical section — insert:**

```python
with lock:
    if key in cache:
        # Another thread inserted this key while we were running the function.
        # The link ordering is already correct; just return our result.
        pass

    elif full:
        # Evict by reusing the oldest node (root[NEXT]) in-place.
        oldroot = root
        oldroot[KEY] = key         # overwrite old sentinel with new data
        oldroot[RESULT] = result

        root = oldroot[NEXT]       # the next-oldest node becomes the new sentinel
        oldkey = root[KEY]
        oldresult = root[RESULT]
        root[KEY] = root[RESULT] = None   # wipe it (it is the new sentinel)

        del cache[oldkey]          # remove evicted entry from dict
        cache[key] = oldroot       # add new entry pointing to recycled node

    else:
        # Cache not full: allocate a new node and append it.
        last = root[PREV]
        link = [last, root, key, result]
        last[NEXT] = root[PREV] = cache[key] = link
        full = (cache_len() >= maxsize)
```

The `full` eviction path is deliberately clever: instead of allocating a new
node and freeing the old one, it reuses the oldest node's memory by writing the
new key/result into it, then rotates `root` forward by one position. The old
sentinel becomes a regular node, and the old LRU node becomes the new sentinel.
This avoids one allocation and one deallocation per eviction.

#### `cache_clear()` (lines 703–710)

```python
def cache_clear():
    nonlocal hits, misses, full
    with lock:
        cache.clear()
        root[:] = [root, root, None, None]   # reset list to empty
        hits = misses = 0
        full = False
```

---

## Part 2 — `_functoolsmodule.c`: the C side

The C implementation mirrors the Python logic but uses C structs for the linked
list nodes and a Python `dict` for the cache. All cached Python objects are
reference-counted manually.

### Data structures

#### `lru_list_elem` (line 1175)

```c
typedef struct lru_list_elem {
    PyObject_HEAD                       // ref count + type pointer
    struct lru_list_elem *prev, *next;  // borrowed links (not ref-counted)
    Py_hash_t hash;                     // cached hash of the key
    PyObject *key, *result;             // owned references
} lru_list_elem;
```

The `prev`/`next` pointers are described as "borrowed" because the dict holds
the owning reference to each node. The linked list itself only has weak
(non-owning) pointers to the nodes it traverses.

`hash` is stored here so that every dict lookup can use the
`_KnownHash` variants of the dict API, avoiding repeated calls to `__hash__`.

#### `lru_cache_object` (line 1211)

```c
typedef struct lru_cache_object {
    lru_list_elem root;              // sentinel node, embedded (not a pointer)
    lru_cache_ternaryfunc wrapper;   // function pointer: which variant to call
    int typed;
    PyObject *cache;                 // dict: key → lru_list_elem
    Py_ssize_t hits;
    PyObject *func;                  // the original user function
    Py_ssize_t maxsize;              // -1 means None (unbounded)
    Py_ssize_t misses;
    PyObject *kwd_mark;              // sentinel object inserted between args/kwargs in key
    PyTypeObject *lru_list_elem_type;
    PyObject *cache_info_type;
    PyObject *dict;                  // instance __dict__ (for attribute access)
    PyObject *weakreflist;
} lru_cache_object;
```

---

### `lru_cache_new()` — object construction (line 1614)

Called when Python evaluates `_lru_cache_wrapper(func, maxsize, typed, CacheInfo)`.

```c
// 1. Parse the four arguments.
PyArg_ParseTupleAndKeywords(args, kw, "OOpO:lru_cache", keywords,
                             &func, &maxsize_O, &typed, &cache_info_type);

// 2. Select the wrapper function pointer based on maxsize.
if (maxsize_O == Py_None)
    wrapper = infinite_lru_cache_wrapper;
else if (maxsize == 0)
    wrapper = uncached_lru_cache_wrapper;
else
    wrapper = bounded_lru_cache_wrapper;

// 3. Create the cache dict.
cachedict = PyDict_New();

// 4. Allocate and initialize the lru_cache_object.
obj->root.prev = &obj->root;     // sentinel points to itself (empty list)
obj->root.next = &obj->root;
obj->wrapper   = wrapper;
obj->cache     = cachedict;
obj->func      = Py_NewRef(func);
obj->hits = obj->misses = 0;
obj->maxsize   = maxsize;        // stored as -1 when None
```

The wrapper function pointer is fixed at construction time. Every subsequent call
dispatches through it with no conditional overhead.

---

### `lru_cache_call()` — the `tp_call` slot (line 1739)

This is what CPython invokes when you write `f(x)` and `f` is an
`lru_cache_object`:

```c
static PyObject *
lru_cache_call(PyObject *op, PyObject *args, PyObject *kwds)
{
    lru_cache_object *self = lru_cache_object_CAST(op);
    return self->wrapper(self, args, kwds);   // direct function-pointer dispatch
}
```

No branching on `maxsize` here — that decision was made once in `lru_cache_new`.

---

### `lru_cache_make_key()` — key construction (line 1231)

Three cases in order of frequency:

**Fast path** — single positional arg, no kwds, no typed, scalar type:

```c
if (!typed && !kwds_size) {
    if (PyTuple_GET_SIZE(args) == 1) {
        key = PyTuple_GET_ITEM(args, 0);
        if (PyUnicode_CheckExact(key) || PyLong_CheckExact(key))
            return Py_NewRef(key);   // use the scalar directly, skip tuple wrapping
    }
    return Py_NewRef(args);          // use the args tuple as-is
}
```

For `f("hello")` or `f(42)`, the key is the scalar object itself, not a
one-element tuple. This avoids one tuple allocation on the most common calls.

**General path** — kwds or typed mode:

Builds a new tuple whose layout is:
```
(arg0, arg1, ..., kwd_mark, kw_name0, kw_val0, kw_name1, kw_val1, ...,
 type(arg0), type(arg1), ..., type(kw_val0), ...)
```

`kwd_mark` is a unique sentinel object stored in the module state that separates
positional arguments from keyword arguments in the key tuple, so `f(1, y=2)` and
`f(1, 2)` produce different keys.

When `typed=True`, the type objects of each argument are appended so that
`f(1)` and `f(1.0)` produce different keys even though `1 == 1.0`.

---

### `uncached_lru_cache_wrapper()` — maxsize == 0 (line 1292)

```c
FT_ATOMIC_ADD_SSIZE(self->misses, 1);
result = PyObject_Call(self->func, args, kwds);
return result;
```

`FT_ATOMIC_ADD_SSIZE` is a macro that resolves to an atomic increment under
free-threaded Python and a plain `+=` under the GIL. No cache interaction at all.

---

### `infinite_lru_cache_wrapper()` — maxsize == None (line 1304)

```c
PyObject *key = lru_cache_make_key(self->kwd_mark, args, kwds, self->typed);
Py_hash_t hash = PyObject_Hash(key);

// dict lookup with pre-computed hash — skips calling __hash__ again
int res = _PyDict_GetItemRef_KnownHash(self->cache, key, hash, &result);

if (res > 0) {             // hit
    FT_ATOMIC_ADD_SSIZE(self->hits, 1);
    Py_DECREF(key);
    return result;
}

// miss
FT_ATOMIC_ADD_SSIZE(self->misses, 1);
result = PyObject_Call(self->func, args, kwds);

_PyDict_SetItem_KnownHash(self->cache, key, result, hash);
Py_DECREF(key);
return result;
```

No list management because there is nothing to evict. The `_KnownHash` variants
pass the already-computed hash directly into the dict internals, avoiding a
second `__hash__` call on the key.

---

### `bounded_lru_cache_wrapper()` — the main case (line 1583)

Structured identically to the Python version: two critical sections around the
user function call.

```c
Py_BEGIN_CRITICAL_SECTION(self);
res = bounded_lru_cache_get_lock_held(self, args, kwds, &result, &key, &hash);
Py_END_CRITICAL_SECTION();

if (res > 0) return result;  // cache hit, done

result = PyObject_Call(self->func, args, kwds);  // user function, no lock

Py_BEGIN_CRITICAL_SECTION(self);
result = bounded_lru_cache_update_lock_held(self, result, key, hash);
Py_END_CRITICAL_SECTION();

return result;
```

`Py_BEGIN/END_CRITICAL_SECTION` are no-ops under the GIL and acquire a
per-object mutex under free-threaded Python (PEP 703). The design intentionally
releases the lock while calling the user function so that other threads can read
the cache concurrently.

#### `bounded_lru_cache_get_lock_held()` — the hit path (line 1401)

```c
// Build key and hash once.
PyObject *key_ = lru_cache_make_key(self->kwd_mark, args, kwds, self->typed);
Py_hash_t hash_ = PyObject_Hash(key_);

// Look up in dict — returns the lru_list_elem node, not the result directly.
int res = _PyDict_GetItemRef_KnownHash_LockHeld(self->cache, key_, hash_,
                                                 (PyObject **)&link);
if (res > 0) {
    // Hit: move node to MRU end.
    lru_cache_extract_link(link);      // remove from current position
    lru_cache_append_link(self, link); // re-insert just before root

    *result = link->result;
    FT_ATOMIC_ADD_SSIZE(self->hits, 1);
    Py_INCREF(link->result);
    Py_DECREF(link);
    Py_DECREF(key_);
    return 1;
}

FT_ATOMIC_ADD_SSIZE(self->misses, 1);
return 0;
```

The dict maps `key → lru_list_elem*`. The result is retrieved from
`link->result`, not stored directly in the dict. The node is moved to the MRU
position by extract + append.

#### `bounded_lru_cache_update_lock_held()` — the miss path (line 1437)

**Race check:** another thread may have inserted the same key while this thread
was executing the user function.

```c
res = _PyDict_GetItemRef_KnownHash_LockHeld(self->cache, key, hash, &testresult);
if (res > 0) {
    // Key was inserted concurrently. Discard our result; the other thread's
    // result is already in place (and list ordering is already updated).
    Py_DECREF(testresult);
    Py_DECREF(key);
    return result;   // return our computed value (equivalent to the cached one)
}
```

**Not full — allocate a new node:**

```c
if (PyDict_GET_SIZE(self->cache) < self->maxsize || self->root.next == &self->root) {
    link = (lru_list_elem *)PyObject_New(lru_list_elem, self->lru_list_elem_type);
    link->hash   = hash;
    link->key    = key;       // steal reference
    link->result = result;    // steal reference
    _PyDict_SetItem_KnownHash_LockHeld(self->cache, key, (PyObject *)link, hash);
    lru_cache_append_link(self, link);   // insert at MRU end
    return Py_NewRef(result);
}
```

**Full — evict oldest and reuse its node:**

```c
// The LRU node is root.next (oldest entry).
link = self->root.next;
lru_cache_extract_link(link);   // remove from list (does NOT free it)

// Remove from dict. This drops the dict's owning reference but we still hold
// the link pointer (from the list traversal), so refcount stays > 0.
_PyDict_Pop_KnownHash(self->cache, link->key, link->hash, &popresult);

// Hold refs to old key and result to prevent __del__ from running during
// the next steps while the node is in a half-updated state.
oldkey    = link->key;
oldresult = link->result;

// Overwrite the node in-place with the new entry.
link->hash   = hash;
link->key    = key;
link->result = result;

// Insert into dict and back into the list at the MRU end.
_PyDict_SetItem_KnownHash_LockHeld(self->cache, key, (PyObject *)link, hash);
lru_cache_append_link(self, link);

// Now it is safe to drop refs to the old data.
Py_DECREF(popresult);
Py_DECREF(oldkey);
Py_DECREF(oldresult);
return Py_NewRef(result);
```

The "hold old refs before overwriting" pattern mirrors the Python version's
comment about preventing `__del__` from running mid-update. In C this matters
because a `Py_DECREF` that drops an object's refcount to zero can execute
arbitrary Python code (`__del__`), which could call back into the cache.

---

### Linked-list primitives (lines 1341–1368)

These are the three pointer-surgery helpers. The list is circular and
doubly-linked; `root` is the sentinel.

#### `lru_cache_extract_link()` — remove a node from wherever it is

```c
lru_list_elem *link_prev = link->prev;
lru_list_elem *link_next = link->next;
link_prev->next = link_next;
link_next->prev = link_prev;
// link->prev and link->next are now stale but will be overwritten before use.
```

#### `lru_cache_append_link()` — insert at MRU end (just before root)

```c
lru_list_elem *root = &self->root;
lru_list_elem *last = root->prev;   // current last (MRU) node
last->next = root->prev = link;
link->prev = last;
link->next = root;
```

After this, `root.prev → link → last → ... → root`.

#### `lru_cache_prepend_link()` — insert at LRU end (just after root)

```c
lru_list_elem *root = &self->root;
lru_list_elem *first = root->next;  // current first (LRU) node
first->prev = root->next = link;
link->prev = root;
link->next = first;
```

Used only for error recovery (restoring an evicted node when `_PyDict_Pop`
fails).

---

### `cache_info` and `cache_clear` (lines 1764–1813)

#### `cache_info`

```c
return PyObject_CallFunction(_self->cache_info_type, "nnnn",
    FT_ATOMIC_LOAD_SSIZE_RELAXED(_self->hits),
    FT_ATOMIC_LOAD_SSIZE_RELAXED(_self->misses),
    _self->maxsize,
    PyDict_GET_SIZE(_self->cache));
```

`FT_ATOMIC_LOAD_SSIZE_RELAXED` is a non-synchronized read under free-threaded
Python; it's acceptable here because `cache_info` is not required to be
perfectly consistent, only approximately correct.

#### `cache_clear`

```c
lru_list_elem *list = lru_cache_unlink_list(self);   // detach entire list
PyDict_Clear(self->cache);                           // wipe dict
_self->hits = _self->misses = 0;
lru_cache_clear_list(list);                          // Py_DECREF each node
```

The list is fully detached before the decrefs happen, so no cache re-entry can
occur during cleanup.

---

## Part 3 — This project's `src/lru_memoize.py`

For comparison, here is how the same three operations map to this project's
`OrderedDict`-based implementation:

| Operation | CPython C | CPython Python | This project |
|---|---|---|---|
| Cache lookup | `_PyDict_GetItemRef_KnownHash` | `cache_get(key)` | `args in cache` |
| Move to MRU | `extract_link` + `append_link` | 6 pointer assignments | `cache.move_to_end(args)` |
| Evict LRU | overwrite oldest node in-place | rotate `root` forward | `cache.popitem(last=False)` |
| Key | scalar or tuple, kwds folded in | same | `args` tuple only |
| Hash caching | yes (`link->hash`) | no | no |
| Thread safety | critical-section macros | `RLock` | none |
| Typed keys | yes | yes | no |

`OrderedDict.move_to_end()` is itself implemented in C and calls the same
kind of doubly-linked-list pointer surgery internally, but it goes through an
extra Python-object layer. The CPython implementation avoids this by managing
the list nodes directly inside `lru_cache_object`.

The key structural simplification in `lru_memoize.py` is that `OrderedDict`
bundles the dict and the ordering list into one object, whereas both CPython
implementations keep them separate (`cache` dict + `root` linked list) to get
direct O(1) control over node placement without going through `OrderedDict`'s
interface.
