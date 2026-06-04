# cfg-guided-decompiler

**Enhancing Neural Decompilation through Linear-Text Augmentation (LTA)**

A token-efficient prompt architecture that injects Control Flow Graph (CFG) structure into LLM-based C++ decompilation. This repository contains the full experimental pipeline for an ablation study comparing three prompting strategies — **BASE**, **DOT**, and **LTA** — across 656 C++ samples.

> **TL;DR:** Verbose CFG formats like Graphviz DOT improve decompilation accuracy but blow past context limits and cause Out-of-Memory failures on constrained hardware. LTA is a compressed, inline topological tagging scheme that preserves CFG structure at a fraction of the token cost. On Gemini 2.5 Flash, **instructed LTA raises the executable rate from 25.6% (BASE) to 32.3%**, a difference validated by McNemar's test (p = 0.0012).

---

## Motivation

Compilation is lossy — variable names, types, and structural boundaries are discarded, making decompilation hard. LLMs recover semantic naturalness well but hallucinate on non-linear control flow and heavily-optimized C++ STL code, because they process assembly as a flat linear stream.

Injecting CFG metadata helps, but standard formats (DOT, JSON) are token-heavy. In VRAM-constrained settings this exhausts the context window, triggers "lost-in-the-middle" attention drift, and causes OOM inference failures.

**LTA (Linear-Text Augmentation)** addresses this by embedding minimal topological tags directly inline with the assembly stream, rather than appending a separate verbose graph declaration.

---

## The three representations

| Mode | CFG input | Notes |
|------|-----------|-------|
| **BASE** | None | Raw disassembled instruction sequence (control group) |
| **DOT** | Graphviz DOT | Explicit nodes + directed edges; semantically unambiguous but verbose |
| **LTA** | Inline tags | Compressed topological tags interleaved with instructions |

### LTA format example

```
[BLOCK: 00000063]
  00000063 MOVSXD RSI,dword ptr [RBP + -0x38]
  00000067 MOV RDI,qword ptr [RBP + -0x58]
  0000006b CALL 0x000001e0
  -> UNCONDITIONAL_CALL: 000001e0
  -> CONDITIONAL_JUMP: 000000d2
  -> FALL_THROUGH: 00000082
```

A key finding (see ablation below) is that the LLM must also be given an explicit **format specification** describing this syntax — the tags alone are not enough.

---

## Key findings

**1. Instructed LTA wins on general-purpose LLMs (Gemini 2.5 Flash, 656 samples)**

| Format | R_exec (%) | R_comp (%) |
|--------|:----------:|:----------:|
| BASE | 25.6 | 58.3 |
| DOT | 28.8 | 58.2 |
| **LTA** | **32.3** | **60.5** |

**2. The advantage holds across all optimization levels (O0–O3)**

LTA maintains a consistent ~+7.9% absolute R_exec margin over BASE at both O0 and O3, surviving aggressive inlining and loop unrolling.

**3. Format specification is required — the headline ablation result**

Without the explicit format spec, "uninstructed" LTA reaches only 28.0% R_exec — statistically indistinguishable from BASE (p = 0.247) and from uninstructed DOT (p = 1.000). The structural advantage only activates when the model is told how to read the tags.

**4. LTA reduces OOM failures**

On an NVIDIA L4 (24 GB VRAM, 16,384-token limit), DOT caused 60 OOM failures vs. 45 for LTA. The LTA failures were a strict subset of the DOT failures — LTA rescued 15 complex O3 functions that crashed under DOT and introduced zero new format-induced errors.

**5. Specialized models behave differently**

LLM4Decompile (a fine-tuned neural decompiler) saw a performance *collapse* with any structural augmentation — both DOT and LTA underperformed raw BASE assembly, regardless of instruction. CFG augmentation helps general-purpose reasoners, not specialized end-to-end decompilers.

---

## Requirements

- Python 3.10+
- [Ghidra](https://ghidra-sre.org/) (headless mode; set `$GHIDRA_HEADLESS`)
- `g++` with C++17 support
- Gemini backend: Google Vertex AI credentials
- Local backend: [vLLM](https://github.com/vllm-project/vllm) serving `LLM4Binary/llm4decompile-9b-v2`

```bash
pip install tqdm statsmodels google-cloud-aiplatform openai
```

---

## Pipeline

### 1. Compile dataset sources to object files
```bash
python compile_source.py
```
Compiles each C++ function at its optimization level (O0–O3) into `.o` files in `compiled_objects/`.

### 2. Extract CFG via Ghidra (batch headless)
```bash
export GHIDRA_HEADLESS=/path/to/ghidra/support/analyzeHeadless
python batch_run_ghidra.py
```
Runs Ghidra headless on each `.o`, invoking `export_cfg_lta.py` (LTA) or `extract_cfg_headless.py` (DOT) to produce per-function CFG files in `cfg_outputs/`.

### 3. (Optional) Convert DOT → LTA
```bash
python generate_lta_from_dot.py
```
Converts DOT-format CFGs in the dataset into LTA format, writing a new `*-LTA.jsonl`.

### 4. Run the ablation study
```bash
python llm_decompile_ablation.py      # Gemini (Vertex AI)
python llm_decompile_ablation_l4.py   # local vLLM / llm4decompile-9b-v2
```
Writes one `ablation_results/outputs_{mode}.jsonl` per mode.

### 5. Evaluate
```bash
bash run_eval.sh
```
Reports R_comp and R_exec by optimization level; extracted C++ saved to `reveal_results/` for inspection. For the full HumanEval benchmark: `python evaluate.py --outputs ...`.

### 6. Statistical significance
```bash
bash run_mcnemar.sh
```
Pairwise McNemar's tests (BASE vs DOT, BASE vs LTA, DOT vs LTA).

---

## Repository layout

| File | Purpose |
|------|---------|
| `compile_source.py` | Compile dataset C++ → object files |
| `batch_run_ghidra.py` | Drive Ghidra headless over all objects |
| `export_cfg_lta.py` | Ghidra script: emit LTA-format CFG |
| `extract_cfg_headless.py` | Ghidra script: emit DOT-format CFG |
| `generate_lta_from_dot.py` | Convert DOT → LTA |
| `llm_decompile_ablation.py` | Ablation runner (Gemini / Vertex AI) |
| `llm_decompile_ablation_l4.py` | Ablation runner (local vLLM) |
| `llm_decompile.py` | Single-file decompile demo (Chain-of-Thought prompt) |
| `evaluate.py` | Evaluate against full HumanEval-Decompile-cpp |
| `evaluate_reveal.py` | Evaluate + dump extracted C++ for inspection |
| `evaluate_mcnemar.py` | McNemar's test across modes |
| `merge_cpp.py` | Concatenate extracted C++ files for review |
| `load_dataset.py` | Dataset loading / exploration demo |

---

## Metrics

| Metric | Definition |
|--------|-----------|
| **R_comp** | Decompiled code compiles with `g++ -std=c++17 -O0` |
| **R_exec** | Compiled binary passes all original unit tests (exit code 0) |

## Dataset

Built on [HumanEval-Decompile-cpp](https://huggingface.co/datasets/LLM4Binary/HumanEval-Decompile): 164 unique C++ functions (curated for complex STL usage) × 4 optimization levels = 656 samples. Each record includes original source, x86-64 assembly, Ghidra pseudocode, and unit tests.

## Evaluated models

- **Gemini 2.5 Flash** (general-purpose, via API) — zero-shot structural reasoning
- **LLM4Decompile** (specialized, via vLLM on NVIDIA L4 24 GB, 16,384-token limit)
