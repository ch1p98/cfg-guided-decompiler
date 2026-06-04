#!/usr/bin/env python3
import json
import argparse
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Tuple
from statsmodels.stats.contingency_tables import mcnemar


def extract_code_from_llm_output(text: str) -> str:
    if not text or not text.strip():
        return text
    match = re.search(r"```(?:cpp|c\+\+)?\s*\n(.*?)```",
                      text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def compile_and_run(func_dep, refined_code, test_code, tmp_dir, compiler="g++", run_timeout=60):
    src = f"{func_dep}\n\n{refined_code}\n\n{test_code}"
    src_path = tmp_dir / "eval.cpp"
    bin_path = tmp_dir / "eval"
    src_path.write_text(src, encoding="utf-8")
    try:
        comp = subprocess.run([compiler, "-std=c++17", "-O0", "-o", str(
            bin_path), str(src_path)], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return False, False, "compile Timeout"
    if comp.returncode != 0:
        return False, False, "compile failed"
    try:
        run_result = subprocess.run(
            [str(bin_path)], capture_output=True, text=True, timeout=run_timeout, cwd=str(tmp_dir))
        return True, run_result.returncode == 0, ""
    except subprocess.TimeoutExpired:
        return True, False, "run Timeout"


def evaluate_file(outputs_path, data_by_idx, compiler, run_timeout):
    results = {}  # { idx_opt: R_exec (1/0) }
    print(f"[*] Compiling and evaluating: {outputs_path}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with open(outputs_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                idx = item.get("index")
                opt = item.get("opt_level", "O0")
                key = f"{idx}_{opt}"

                refined_raw = (item.get("refined_code") or "").strip()
                refined = extract_code_from_llm_output(
                    refined_raw) or refined_raw
                data_rec = data_by_idx.get(idx, {})
                func_dep = data_rec.get(
                    "func_dep", "#include <bits/stdc++.h>\nusing namespace std;\n")
                test_code = data_rec.get("test", "int main() { return 0; }")

                _, r_exec, _ = compile_and_run(
                    func_dep, refined, test_code, tmp_path, compiler, run_timeout)
                results[key] = 1 if r_exec else 0
    return results


def compare_models(name1, res1, name2, res2):
    """Run McNemar's test between two result sets."""
    both_pass = 0
    both_fail = 0
    m1_only = 0
    m2_only = 0

    common_keys = set(res1.keys()).intersection(set(res2.keys()))
    print(f"\n{'-'*50}")
    print(f"[*] McNemar's Test: {name1} vs {name2}  (n={len(common_keys)})")
    print(f"{'-'*50}")

    for key in common_keys:
        p1 = res1[key]
        p2 = res2[key]
        if p1 and p2:
            both_pass += 1
        elif not p1 and not p2:
            both_fail += 1
        elif p1 and not p2:
            m1_only += 1
        elif not p1 and p2:
            m2_only += 1

    table = [[both_pass, m1_only],
             [m2_only, both_fail]]

    print(f"Both pass:       {both_pass}")
    print(f"Both fail:       {both_fail}")
    print(f"{name1} only:   {m1_only}")
    print(f"{name2} only:   {m2_only}")

    result = mcnemar(table, exact=False, correction=True)
    print(f"\n=> P-value: {result.pvalue:.6f}")
    if result.pvalue < 0.05:
        print(f"[SIGNIFICANT]   p < 0.05 — {name1} vs {name2} difference is statistically significant.")
    else:
        print(f"[NOT SIGNIFICANT] p >= 0.05 — difference is not statistically significant.")


def main():
    parser = argparse.ArgumentParser(
        description="McNemar's Test for Base vs DOT vs LTA")
    parser.add_argument("--base", required=True, help="Path to BASE outputs jsonl")
    parser.add_argument("--dot", required=True, help="Path to DOT outputs jsonl")
    parser.add_argument("--lta", required=True, help="Path to LTA outputs jsonl")
    parser.add_argument("--dataset", required=True, help="Reference dataset JSONL path")
    args = parser.parse_args()

    # 1. Load reference dataset
    data_by_idx = {}
    with open(args.dataset, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                data_by_idx[int(rec["index"])] = rec

    # 2. Evaluate BASE, DOT, LTA and collect R_exec results
    print("[*] Starting evaluation engine — extracting and compiling C++ code...")
    base_results = evaluate_file(args.base, data_by_idx, "g++", 60)
    dot_results  = evaluate_file(args.dot,  data_by_idx, "g++", 60)
    lta_results  = evaluate_file(args.lta,  data_by_idx, "g++", 60)

    # 3. Run all three pairwise comparisons
    compare_models("BASE", base_results, "DOT", dot_results)
    compare_models("BASE", base_results, "LTA", lta_results)
    compare_models("DOT",  dot_results,  "LTA", lta_results)


if __name__ == "__main__":
    main()
