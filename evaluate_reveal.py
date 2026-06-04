#!/usr/bin/env python3
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
import os
import tempfile
import sys
import subprocess
import re
import json
import csv
import argparse
"""
Evaluate and Reveal decompilation results.
Evaluates decompilation quality and saves LLM-extracted C++ code to disk for manual inspection.
"""


def iter_jsonl(path):
    """Iterate over records in a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_by_index(path):
    """Build an index of dataset records keyed by index field."""
    return {int(rec["index"]): rec for rec in iter_jsonl(path)}


def extract_code_from_llm_output(text: str) -> str:
    """Strip Markdown code fences from LLM output and return raw C++ code."""
    if not text or not text.strip():
        return text
    # Try ```cpp ... ``` or ```c++ ... ```
    match = re.search(r"```(?:cpp|c\+\+)?\s*\n(.*?)```",
                      text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Fall back to generic ``` ... ```
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
    """Compile and execute the decompiled code. Returns (R_comp, R_exec, error_msg)."""
    src = f"{func_dep}\n\n{refined_code}\n\n{test_code}"
    src_path = tmp_dir / "eval.cpp"
    bin_path = tmp_dir / "eval"
    src_path.write_text(src, encoding="utf-8")

    try:
        # Compile with C++17
        comp = subprocess.run(
            [compiler, "-std=c++17", "-O0", "-o",
                str(bin_path), str(src_path)],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, False, "compile TimeoutExpired"

    if comp.returncode != 0:
        return False, False, (comp.stderr or comp.stdout or "")[:500]

    try:
        # Execute compiled binary
        run_result = subprocess.run(
            [str(bin_path)], capture_output=True, text=True,
            timeout=run_timeout, cwd=str(tmp_dir),
        )
        return True, run_result.returncode == 0, ""
    except subprocess.TimeoutExpired:
        return True, False, "run TimeoutExpired"


def main():
    # Default to the 32-sample test dataset
    default_dataset = "test-cpp-LTA.jsonl"

    parser = argparse.ArgumentParser(
        description="Evaluate and reveal extracted C++ code.")
    parser.add_argument("--outputs", required=True,
                        help="Path to LLM outputs.jsonl")
    parser.add_argument("--dataset", default=default_dataset,
                        help="Reference dataset JSONL path")
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--run-timeout", type=int, default=60)
    args = parser.parse_args()

    outputs_path = Path(args.outputs)
    dataset_path = Path(args.dataset)

    if not outputs_path.exists():
        print(f"ERROR: Output file not found: {outputs_path}")
        return 1
    if not dataset_path.exists():
        print(f"ERROR: Dataset file not found: {dataset_path}")
        return 1

    ts_match = re.search(r"(\d{8}_\d{6})", outputs_path.name)
    if ts_match:
        timestamp = ts_match.group(1)
    else:
        # Fall back to current timestamp if none found in filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load reference dataset
    data_by_idx = load_by_index(dataset_path)

    # ---------------------------------------------------------
    # Build reveal directory structure
    # ---------------------------------------------------------
    group_name = "unknown"
    fn_lower = outputs_path.name.lower()
    if "base" in fn_lower:
        group_name = "base"
    elif "dot" in fn_lower:
        group_name = "dot"
    elif "lta" in fn_lower:
        group_name = "lta"

    reveal_dir = Path(f"reveal_results") / group_name
    reveal_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Experiment mode detected: {group_name.upper()}")
    print(f"[*] Timestamp: {timestamp}")
    print(f"[*] Extracted C++ code will be saved to: {reveal_dir}")

    per_sample: List[dict] = []
    opt_counts: Dict[str, int] = {}
    opt_exec: Dict[str, int] = {}
    opt_comp: Dict[str, int] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        n = 0
        for item in iter_jsonl(outputs_path):
            idx = item.get("index")
            refined_raw = (item.get("refined_code") or "").strip()

            # Extract and clean code
            refined = extract_code_from_llm_output(refined_raw) or refined_raw
            opt = item.get("opt_level", "O0")

            # Save extracted code to disk (overwrite if exists)
            save_path = reveal_dir / f"{idx}_{opt}.cpp"
            save_path.write_text(refined, encoding="utf-8")

            data_rec = data_by_idx.get(idx, {})
            func_dep = data_rec.get(
                "func_dep", "#include <bits/stdc++.h>\nusing namespace std;\n")
            test_code = data_rec.get("test", "int main() { return 0; }")

            r_comp, r_exec, err = compile_and_run(
                func_dep, refined, test_code, tmp_path, args.compiler, args.run_timeout
            )

            opt_counts[opt] = opt_counts.get(opt, 0) + 1
            opt_exec[opt] = opt_exec.get(opt, 0) + (1 if r_exec else 0)
            opt_comp[opt] = opt_comp.get(opt, 0) + (1 if r_comp else 0)

            per_sample.append({
                "index": idx,
                "opt_level": opt,
                "R_comp": 1 if r_comp else 0,
                "R_exec": 1 if r_exec else 0,
            })

            n += 1
            if n % 10 == 0:
                print(f"  Evaluated {n} samples...")

    # Print summary report
    total = len(per_sample)
    if total == 0:
        print("No evaluable records found.")
        return 1

    print(f"\n{'='*50}")
    print(f"Ablation Study Results (Mode: {group_name.upper()})")
    print(f"{'='*50}")

    print(
        f"  Overall R_exec: {sum(p['R_exec'] for p in per_sample)/total:.1%}")
    print(
        f"  Overall R_comp: {sum(p['R_comp'] for p in per_sample)/total:.1%}")

    # Per-optimization-level breakdown (O0~O3)
    print("\n  --- Per-optimization-level breakdown ---")
    for opt_level in sorted(opt_counts.keys()):
        count = opt_counts[opt_level]
        if count > 0:
            comp_rate = opt_comp.get(opt_level, 0) / count
            exec_rate = opt_exec.get(opt_level, 0) / count
            print(
                f"  [{opt_level}] Samples: {count:3d} | R_comp: {comp_rate:>5.1%} | R_exec: {exec_rate:>5.1%}")

    print(f"\n[*] Code files saved to: {reveal_dir.absolute()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
