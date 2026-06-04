import asyncio
from datetime import datetime
import time
import os
import random
import json
from tqdm import tqdm
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize Vertex AI
vertexai.init(project="project-68418f97-dded-4817-87c", location="us-central1")
model = GenerativeModel(model_name="gemini-2.5-flash")

# ==========================================
# Experiment configuration
# ==========================================
# DATASET_PATH = "test_sample_32_LTA.jsonl"
DATASET_PATH = "test-cpp-LTA.jsonl"
OUT_DIR = "ablation_results"
os.makedirs(OUT_DIR, exist_ok=True)

EXPERIMENT_MODES = ["base", "dot", "lta"]
CONCURRENCY_LIMIT = 8


def get_cfg_content(mode, record):
    if mode == "base":
        return ""
    elif mode == "dot":
        return record.get("cfg_dot", "// DOT File Not Found")
    elif mode == "lta":
        return record.get("cfg_lta", "// LTA File Not Found")


def build_prompt(mode, asm_code, cfg_content):
    instruction_header = f"This is the given assembly code:\n<ASM_INPUT>\n{asm_code}\n</ASM_INPUT>\n"
    target_question = "\nWhat is the source C++ code?"

    if mode == "base":
        return instruction_header + target_question
    elif mode == "dot":
        cfg_section = f"\n### Auxiliary Information: Control Flow Graph (DOT Format)\n<DOT_CFG>\n{cfg_content}\n</DOT_CFG>\n"
        return instruction_header + cfg_section + target_question
    elif mode == "lta":
        lta_description = """\n
### LTA Format Specification:
The provided Control Flow Graph is in Linearized Tagged Assembly (LTA) format:
1. `[BLOCK: address]` marks the beginning of a basic block.
2. `-> UNCONDITIONAL_JUMP/CONDITIONAL_JUMP/FALL_THROUGH`: These tags define the control flow edges.
Use this structural information to reconstruct logic like if-else, loops, and function calls.
"""
        lta_description = ""  # Ablation: withhold LTA format description to isolate its effect on results
        cfg_section = f"{lta_description}\n### Auxiliary Information: CFG (LTA Format)\n<LTA_CFG>\n{cfg_content}\n</LTA_CFG>\n"
        return instruction_header + cfg_section + target_question


async def process_single_record(mode, record, pbar):
    """Process a single record asynchronously with exponential backoff retry and timeout."""
    idx = record.get("index", -1)
    opt = record.get("opt", "unknown")
    asm_code = record.get("asm", "")

    cfg_content = get_cfg_content(mode, record)
    prompt = build_prompt(mode, asm_code, cfg_content)
    max_retries = 7

    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(prompt),
                timeout=527.0
            )
            return {
                "index": idx,
                "opt_level": opt,
                "refined_code": response.text,
                "status": "OK"
            }
        except asyncio.TimeoutError:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            # Use pbar.write to avoid corrupting the progress bar rendering
            pbar.write(f"  [!] Index {idx} timed out. Retry {attempt+1} in {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ["429", "resource exhausted", "503"]):
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)
            else:
                return {
                    "index": idx, "opt_level": opt,
                    "refined_code": "// DECOMPILATION FAILED",
                    "status": f"ERROR: {e}"
                }
    return {"index": idx, "opt_level": opt, "refined_code": "// FAILED", "status": "ERROR: max retries exceeded"}


async def run_ablation_study():
    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: Dataset not found: {DATASET_PATH}")
        return

    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[*] Loaded {len(records)} records. Starting ablation study. Timestamp: {timestamp}\n")

    for mode in EXPERIMENT_MODES:
        if mode == "base":
            continue
        output_file = os.path.join(OUT_DIR, f"outputs_{mode}.jsonl")
        print(f"========== Running mode: [{mode.upper()}] ==========")

        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

        # Progress bar for this mode
        pbar = tqdm(total=len(records), desc=f"Mode: {mode}", unit="sample")

        async def worker(r):
            async with semaphore:
                return await process_single_record(mode, r, pbar)

        tasks = [worker(r) for r in records]

        with open(output_file, "w", encoding="utf-8") as f_out:
            for coro in asyncio.as_completed(tasks):
                result = await coro

                pbar.set_postfix(idx=result['index'], opt=result['opt_level'])
                pbar.update(1)

                f_out.write(json.dumps({
                    "index": result["index"],
                    "opt_level": result["opt_level"],
                    "refined_code": result["refined_code"]
                }, ensure_ascii=False) + "\n")
                f_out.flush()

        pbar.close()

    print(f"\n[*] Ablation study complete.")

if __name__ == "__main__":
    asyncio.run(run_ablation_study())
