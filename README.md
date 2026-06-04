# cfg-guided-decompiler

Token-efficient LLM-based C++ decompilation augmented with Control Flow Graph (CFG) information extracted via Ghidra.

This project implements and evaluates three decompilation prompting strategies — **Base**, **DOT**, and **LTA** — on the [HumanEval-Decompile-cpp](https://huggingface.co/datasets/LLM4Binary/HumanEval-Decompile) benchmark, using McNemar's test to assess statistical significance of differences.

---

## Overview

Standard LLM decompilation prompts only provide raw assembly. This project investigates whether supplying structured CFG information as auxiliary context improves decompilation quality, and whether a token-efficient linearized format (LTA) can match or exceed the richer DOT graph format.

### Prompting modes

| Mode | CFG input | Description |
|------|-----------|-------------|
| **Base** | None | Assembly only |
| **DOT** | DOT graph | Full CFG in Graphviz DOT format |
| **LTA** | LTA format | Linearized Tagged Assembly — a token-efficient CFG representation |

### LTA format

LTA (Linearized Tagged Assembly) represents CFG structure as plain text:

```
[BLOCK: 0x401a20]
  push rbp
  mov rbp, rsp
  -> FALL_THROUGH: 0x401a24

[BLOCK: 0x401a24]
  cmp eax, 0
  -> CONDITIONAL_JUMP: 0x401a40
  -> FALL_THROUGH: 0x401a28
```

---

## Requirements

- Python 3.10+
- [Ghidra](https://ghidra-sre.org/) (headless mode; set `$GHIDRA_HEADLESS` env var)
- `g++` with C++17 support
- For Gemini backend: Google Vertex AI credentials
- For local model backend: [vLLM](https://github.com/vllm-project/vllm) serving `LLM4Binary/llm4decompile-9b-v2`
- Python dependencies:

```bash
pip install tqdm statsmodels google-cloud-aiplatform openai
```

---

## Pipeline

### Step 1 — Compile dataset sources to object files

```bash
python compile_source.py
```

Reads a `.jsonl` dataset, compiles each C++ function at its specified optimization level (`O0`–`O3`), and saves `.o` files to `compiled_objects/`.

### Step 2 — Extract CFG via Ghidra (batch)

```bash
export GHIDRA_HEADLESS=/path/to/ghidra/support/analyzeHeadless
python batch_run_ghidra.py
```

Runs Ghidra headless on each `.o` file and invokes `export_cfg_lta.py` (or `extract_cfg_headless.py` for DOT output) to extract per-function CFG files into `cfg_outputs/`.

### Step 3 — (Optional) Convert DOT → LTA

```bash
python generate_lta_from_dot.py
```

Converts DOT-format CFGs embedded in the dataset into LTA format, writing a new `*-LTA.jsonl` dataset file.

### Step 4 — Run ablation study

**Gemini (Vertex AI) backend:**
```bash
python llm_decompile_ablation.py
```

**Local vLLM backend (llm4decompile-9b-v2):**
```bash
python llm_decompile_ablation_l4.py
```

Outputs one `ablation_results/outputs_{mode}.jsonl` per mode.

### Step 5 — Evaluate results

```bash
bash run_eval.sh
```

Or manually:
```bash
python evaluate_reveal.py \
    --dataset test-cpp-LTA.jsonl \
    --outputs ablation_results/outputs_lta.jsonl
```

Reports **R_comp** (compilation rate) and **R_exec** (functional correctness), broken down by optimization level. Extracted C++ files are saved to `reveal_results/` for manual inspection.

Full evaluation against the original HumanEval-Decompile-cpp benchmark:
```bash
python evaluate.py --outputs ablation_results/outputs_lta.jsonl
```

### Step 6 — Statistical significance (McNemar's test)

```bash
bash run_mcnemar.sh
```

Runs pairwise McNemar's tests across all three modes (Base vs DOT, Base vs LTA, DOT vs LTA).

---

## Output structure

```
ablation_results/
    outputs_base.jsonl
    outputs_dot.jsonl
    outputs_lta.jsonl
reveal_results/
    base/   # extracted .cpp files per sample
    dot/
    lta/
cfg_outputs/
    record_0_O0_func0.lta
    ...
compiled_objects/
    record_0_O0.o
    ...
```

---

## Evaluation metrics

| Metric | Definition |
|--------|-----------|
| **R_comp** | Decompiled code compiles with `g++ -std=c++17 -O0` |
| **R_exec** | Compiled binary passes all unit tests (exit code 0) |

---

## Dataset

Built on [HumanEval-Decompile-cpp](https://huggingface.co/datasets/LLM4Binary/HumanEval-Decompile): 164 unique C++ functions × 4 optimization levels = 656 records. Each record includes original source, x86-64 assembly, Ghidra pseudocode, and unit tests.
