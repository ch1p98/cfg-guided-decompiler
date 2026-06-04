# HumanEval-Decompile-cpp — Usage Guide

## 1. Dataset Overview

The HumanEval-Decompile-cpp dataset contains 656 records (164 unique C++ functions x 4 optimization levels: O0/O1/O2/O3). Each record includes the original C++ source, x86-64 assembly, Ghidra pseudocode, and unit tests for evaluating decompilation quality.

**Dataset file:**
```
humaneval_decompile_guide/HumanEval-Decompile-cpp.jsonl
```

### Fields per record

| Field | Type | Description |
|-------|------|-------------|
| `index` | int | Unique ID (0–655) |
| `func_name` | str | Function name (e.g., `func0`) |
| `opt` | str | Optimization level: `O0`, `O1`, `O2`, `O3` |
| `language` | str | Always `"cpp"` |
| `asm` | str | x86-64 assembly (objdump format) |
| `ghidra_asm` | str | Ghidra-format assembly (uppercase mnemonics) |
| `ghidra_pseudo` | str | Ghidra decompiler pseudocode |
| `func_dep` | str | C++ includes/dependencies needed to compile |
| `test` | str | Unit test code with assertions |
| `func` | str | Original C++ source code |

---

## 2. Loading the Dataset

### Minimal loading (standard library only)

```python
import json

def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

DATASET = "humaneval_decompile_guide/HumanEval-Decompile-cpp.jsonl"

for rec in iter_jsonl(DATASET):
    print(rec["index"], rec["func_name"], rec["opt"])
```

### Index by record ID

```python
import json

def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

DATASET = "humaneval_decompile_guide/HumanEval-Decompile-cpp.jsonl"

data_by_idx = {}
for rec in iter_jsonl(DATASET):
    data_by_idx[rec["index"]] = rec

rec = data_by_idx[0]  # func0, O0
print(rec["func"])           # Original C++ source
print(rec["asm"])            # Assembly
print(rec["ghidra_pseudo"])  # Ghidra pseudocode
```

See also: `humaneval_decompile_guide/load_dataset.py` for a self-contained demo script.

---

## 3. Evaluating Decompilation Results

### What you need

Your decompilation model should produce an `outputs.jsonl` file where each line contains:

```json
{
    "index": 0,
    "opt_level": "O0",
    "refined_code": "bool func0(vector<float> numbers, float threshold) { ... }"
}
```

- `index` must match the dataset record index
- `refined_code` is the decompiled C++ code (can be wrapped in markdown code blocks)

### Metrics

| Metric | What it measures |
|--------|-----------------|
| **R_exec** | Functional correctness — decompiled code compiles AND passes all unit tests |
| **R_comp** | Compilation success rate — decompiled code compiles with `g++ -std=c++17 -O0` |

### Running evaluation

```bash
python3 humaneval_decompile_guide/evaluate.py \
    --outputs /path/to/outputs.jsonl
```

**Outputs:**
- `per_sample.jsonl` — per-record metrics (R_comp, R_exec, compile_error)
- `summary.csv` — aggregate metrics (overall + per optimization level R_exec)

### Evaluation details

The evaluation pipeline for each record:
1. Extracts C++ code from LLM output (strips markdown code blocks if present)
2. Combines `func_dep` (includes) + `refined_code` + `test` (unit tests) into a single `.cpp` file
3. Compiles with `g++ -std=c++17 -O0` (timeout: 30s) — **R_comp**
4. Runs the compiled binary (timeout: 60s), checks exit code == 0 — **R_exec**

See also: `humaneval_decompile_guide/evaluate.py` for the standalone evaluation script.
