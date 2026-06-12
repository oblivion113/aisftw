## COURSE INFO
- AIE310008.01 人工智能的软件基础 Foundations of Software for Artificial Intelligence 
- 2026 Spring

## Content

| Project | Description | Code | Report | Ref |
| :--- | :-----| :--- | :--- | :--- |
|1 (L1-L4)| builds two cache decorators, validates them against `functools.lru_cache`, benchmarks their overhead, and records brief CPython source notes | [LRU memoize](./lru-memoize-project/) | [report](./lru-memoize-project/report/report.md) | [不基础的python基础_@码农高天](https://space.bilibili.com/245645656/lists/346060?type=season) </br> [Python 3.14.3 documentation](https://docs.python.org/3/#)|
|2 (L5-L8)| implements softmax regression for FashionMNIST with both a normal PyTorch baseline and explicit Triton kernels | [manual softmax](./man_softmax/) | [report](./man_softmax/REPORT.md) | [tutorials from triton official site 01-03](https://triton-lang.org/main/getting-started/tutorials/index.html) </br> [Dive-into-DL-Pytorch](https://tangshusen.me/Dive-into-DL-PyTorch/#/) |
|3 (L9-L12)| created a terminal application that stages an unsupervised debate among several large language models | [roundtable](./roundtable/)| [report](./roundtable/REPORT.md) | get the idea from [moltbook](https://www.moltbook.com/) （I don't like openclaw but I think moltbook is cool ）|

## Clone

This repository uses Git submodules for the project folders. Clone it with:

```bash
git clone --recurse-submodules git@github.com:oblivion113/aisftw.git
```

If you already cloned without submodules, run:

```bash
git submodule update --init --recursive
```

Before pushing changes from this local copy, push the submodule repositories first if their commits are new, then push this parent repository.

## NOTE

- most part are vibe coded by claude code and codex
