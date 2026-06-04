#!/usr/bin/env python3
"""Evaluate decompilation results on HumanEval-Decompile-cpp.

Given an outputs.jsonl with decompiled code, this script:
1. Compiles each decompiled function with its dependencies and test code
2. Runs the compiled binary to check functional correctness
3. Reports R_exec and R_comp

Usage:
    python humaneval_decompile_guide/evaluate.py \
        --outputs /path/to/outputs.jsonl

outputs.jsonl format (one JSON object per line):
    {"index": 0, "opt_level": "O0", "refined_code": "bool func0(...) { ... }"}

Required fields:
    - index (int): must match dataset record index
    - refined_code (str): decompiled C++ code (markdown code blocks are auto-stripped)

Optional fields:
    - opt_level (str): for per-optimization breakdown
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_by_index(path):
    return {int(rec["index"]): rec for rec in iter_jsonl(path)}


def extract_code_from_llm_output(text: str) -> str:
    """Strip markdown code blocks from LLM output."""
    if not text or not text.strip():
        return text
    match = re.search(r"```(?:cpp|c\+\+)\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def compile_and_run(
    func_dep: str,
    refined_code: str,
    test_code: str,
    tmp_dir: Path,
    compiler: str = "g++",
    run_timeout: int = 60,
) -> Tuple[bool, bool, str]:
    """Return (R_comp, R_exec, error_msg)."""
    src = f"{func_dep}\n\n{refined_code}\n\n{test_code}"
    src_path = tmp_dir / "eval.cpp"
    bin_path = tmp_dir / "eval"
    src_path.write_text(src, encoding="utf-8")

    try:
        comp = subprocess.run(
            [compiler, "-std=c++17", "-O0", "-o", str(bin_path), str(src_path)],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, False, "compile TimeoutExpired"

    if comp.returncode != 0:
        return False, False, (comp.stderr or comp.stdout or "")[:500]

    try:
        run_result = subprocess.run(
            [str(bin_path)], capture_output=True, text=True,
            timeout=run_timeout, cwd=str(tmp_dir),
        )
        return True, run_result.returncode == 0, ""
    except subprocess.TimeoutExpired:
        return True, False, "run TimeoutExpired"


def main():
    default_dataset = str(Path(__file__).resolve().parent / "HumanEval-Decompile-cpp.jsonl")

    parser = argparse.ArgumentParser(description="Evaluate decompilation results on HumanEval-Decompile-cpp.")
    parser.add_argument("--outputs", required=True, help="Path to outputs.jsonl with decompiled code")
    parser.add_argument("--dataset", default=default_dataset, help="Dataset JSONL")
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--run-timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="Evaluate only first N records (0=all)")
    parser.add_argument("--out-dir", default="", help="Output directory (default: same as outputs.jsonl)")
    args = parser.parse_args()

    outputs_path = Path(args.outputs)
    if not outputs_path.exists():
        print(f"outputs.jsonl not found: {outputs_path}", file=sys.stderr)
        return 1

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    data_by_idx = load_by_index(dataset_path)
    out_dir = Path(args.out_dir) if args.out_dir else outputs_path.parent

    per_sample: List[dict] = []
    opt_counts: Dict[str, int] = {}
    opt_exec: Dict[str, int] = {}
    opt_comp: Dict[str, int] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        n = 0
        for item in iter_jsonl(outputs_path):
            if args.limit and n >= args.limit:
                break

            idx = item.get("index")
            refined_raw = (item.get("refined_code") or "").strip()
            refined = extract_code_from_llm_output(refined_raw) or refined_raw
            opt = item.get("opt_level", "O0")

            data_rec = data_by_idx.get(idx, {})
            func_dep = data_rec.get("func_dep", "#include <bits/stdc++.h>\nusing namespace std;\n")
            test_code = data_rec.get("test", "int main() { return 0; }")

            r_comp, r_exec, err = compile_and_run(
                func_dep, refined, test_code, tmp_path, args.compiler, args.run_timeout
            )

            opt_counts[opt] = opt_counts.get(opt, 0) + 1
            opt_exec[opt] = opt_exec.get(opt, 0) + (1 if r_exec else 0)
            opt_comp[opt] = opt_comp.get(opt, 0) + (1 if r_comp else 0)

            per_sample.append({
                "index": idx, "opt_level": opt,
                "R_comp": 1 if r_comp else 0,
                "R_exec": 1 if r_exec else 0,
                "compile_error": err[:200] if err else "",
            })
            n += 1
            if n % 20 == 0:
                print(f"  Evaluated {n} records...", flush=True)

    total = len(per_sample)
    if total == 0:
        print("No records to evaluate.", file=sys.stderr)
        return 1

    r_comp_rate = sum(p["R_comp"] for p in per_sample) / total
    r_exec_rate = sum(p["R_exec"] for p in per_sample) / total

    # Print results
    print(f"\n{'='*50}")
    print(f"Results ({total} records)")
    print(f"{'='*50}")
    print(f"  R_exec:  {r_exec_rate:.1%}")
    print(f"  R_comp:  {r_comp_rate:.1%}")
    print()
    for opt in ["O0", "O1", "O2", "O3"]:
        c = opt_counts.get(opt, 0)
        if c:
            print(f"  R_exec ({opt}):  {opt_exec.get(opt, 0) / c:.1%}  ({opt_exec.get(opt, 0)}/{c})")

    # Write per_sample.jsonl
    out_dir.mkdir(parents=True, exist_ok=True)
    ps_path = out_dir / "per_sample.jsonl"
    with open(ps_path, "w", encoding="utf-8") as f:
        for row in per_sample:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write summary.csv
    summary_path = out_dir / "summary.csv"
    fieldnames = ["count", "R_exec", "R_comp",
                  "R_exec_O0", "R_exec_O1", "R_exec_O2", "R_exec_O3"]
    summary = {"count": total, "R_exec": r_exec_rate, "R_comp": r_comp_rate}
    for opt in ["O0", "O1", "O2", "O3"]:
        c = opt_counts.get(opt, 0)
        summary[f"R_exec_{opt}"] = opt_exec.get(opt, 0) / c if c else 0
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary)

    print(f"\nWrote: {ps_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
