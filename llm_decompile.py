import os
from datetime import datetime
import google.generativeai as genai

# Import API setup function from our module
from check_models import setup_gemini_api

# ==========================================
# 1. Load API credentials via module
# ==========================================
setup_gemini_api()

# Use gemini-2.5-pro for complex reasoning tasks
model = genai.GenerativeModel('gemini-2.5-pro')

# ==========================================
# 2. Load LTA input data
# ==========================================
print("[*] Loading LTA (Linearized Tagged Assembly) input...")
lta_file = "target_cfg.lta"

if not os.path.exists(lta_file):
    raise FileNotFoundError(
        f"ERROR: {lta_file} not found. Run export_cfg_lta.py via Ghidra Headless first.")

with open(lta_file, "r") as f:
    lta_code = f.read()

# ==========================================
# 3. Build prompt with Chain-of-Thought decompiler pipeline
# ==========================================
# Design rationale: force the LLM into Chain-of-Thought reasoning that mirrors
# the IR transformation stages of a traditional decompiler.
prompt = f"""
You are an expert Decompiler Architect and Senior C++ Reverse Engineer. 
Your task is to decompile the provided ARM64 Linearized Tagged Assembly (LTA) into strictly equivalent, compilable C++17 source code. The original binary was compiled with `clang++ -std=c++17 -O2`.

### PRIORITIES:
1. **Semantic Equivalence:** The generated C++ MUST perfectly mirror the side effects, memory layouts, and data flow of the assembly.
2. **Compilability:** The output must be valid C++17. Use proper typing, referencing, and standard library headers.
3. **Readability:** Recover high-level STL constructs (e.g., `std::string`, `std::shared_ptr`, virtual dispatch) where recognized.

### THE DECOMPILATION PIPELINE (CHAIN-OF-THOUGHT):
You MUST structure your response strictly into the following three stages. Do not skip any stage.

#### Stage 1: ABI & Data Flow Analysis (Pseudo-IR)
Analyze the AAPCS64 calling convention and stack frame layout. Explicitly document:
- **Arguments:** What is passed in x0-x7? Is x0 a `this` pointer (indicating a member function)?
- **Return Value / sret:** Is x8 used as an indirect return pointer for a large struct/class (e.g., `std::string`, custom objects)?
- **Stack Variables:** Identify localized stack offsets (e.g., `[sp, #0x8]`, `[sp, #0x30]`) and infer their sizes/types based on how they are accessed.
- **Virtual Dispatch / Function Pointers:** Note any indirect branches (`blr`) and calculate the vtable offset (e.g., `[x0, #0x20]`).

#### Stage 2: Control Flow Graph (CFG) Structuring
Map the raw LTA blocks and jumps into high-level control flow structures.
- Translate `cbz`, `cbnz`, `b.eq`, etc., into `if/else`, `while`, or `for` loops.
- Resolve any phi-node-like behavior (e.g., `csel` instructions) into ternary operators or conditional assignments.

#### Stage 3: C++ AST Reconstruction
Write the final C++ source code block. 
- You MUST enclose the code in standard ```cpp ... ``` markdown.
- Apply C++17 idioms (RAII, `auto`, structured binding) where appropriate.
- Include necessary hypothetical headers (e.g., `<string>`, `<memory>`).
- If a function call targets an unknown external address, declare a placeholder function or use a `// TODO: unknown_call()` comment, but keep the control flow intact.

### Input Data (LTA Format):
<LTA_INPUT>
{lta_code}
</LTA_INPUT>

Begin the decompilation process now, starting with Stage 1.
"""

# ==========================================
# 4. Call API and collect response
# ==========================================
print("[*] Calling Gemini API for multi-stage semantic reconstruction (this may take a moment)...")
response = model.generate_content(prompt)

# ==========================================
# 5. Save result with timestamp
# ==========================================
current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_filename = f"response_{current_time_str}.cpp"

with open(output_filename, "w") as f:
    f.write(response.text)

print("\n==========================================")
print(f"[*] Decompilation complete. Output saved to: {output_filename}")
print("==========================================\n")
print(response.text)
