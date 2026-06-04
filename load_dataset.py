#!/usr/bin/env python3
"""Demo: Load and explore the HumanEval-Decompile-cpp dataset.

Usage:
    python humaneval_decompile_guide/load_dataset.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

GUIDE_DIR = Path(__file__).resolve().parent
DATASET = GUIDE_DIR / "HumanEval-Decompile-cpp.jsonl"


def iter_jsonl(path):
    """Yield parsed JSON objects from a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_all(path=DATASET):
    """Load all records into a list."""
    return list(iter_jsonl(path))


def load_by_index(path=DATASET):
    """Load records into a dict keyed by index."""
    return {rec["index"]: rec for rec in iter_jsonl(path)}


def main():
    if not DATASET.exists():
        print(f"Dataset not found: {DATASET}", file=sys.stderr)
        return 1

    records = load_all()
    print(f"Total records: {len(records)}")

    # Unique functions and optimization levels
    funcs = {rec["func_name"] for rec in records}
    opts = Counter(rec["opt"] for rec in records)
    print(f"Unique functions: {len(funcs)}")
    print(f"Optimization levels: {dict(opts)}")

    # Show one example record
    rec = records[0]
    print(f"\n--- Example record (index={rec['index']}) ---")
    print(f"func_name: {rec['func_name']}")
    print(f"opt: {rec['opt']}")
    print(f"func_dep: {rec['func_dep'][:100]}...")
    print(f"func (first 200 chars): {rec['func'][:200]}...")
    print(f"asm (first 200 chars): {rec['asm'][:200]}...")
    print(f"ghidra_pseudo (first 200 chars): {rec['ghidra_pseudo'][:200]}...")
    print(f"test (first 200 chars): {rec['test'][:200]}...")

    # Show available fields
    print(f"\nAll fields: {sorted(rec.keys())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
