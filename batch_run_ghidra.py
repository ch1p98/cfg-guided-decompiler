# batch_run_ghidra.py
import os
import subprocess
import shutil

# ==========================================
# Configure your Ghidra installation path here
# ==========================================
GHIDRA_PATH = os.environ.get("GHIDRA_HEADLESS")
if not GHIDRA_PATH:
    GHIDRA_PATH = "/Applications/ghidra_12.0.1_PUBLIC/support/analyzeHeadless"
    print("WARNING: $GHIDRA_HEADLESS environment variable not set. Using hardcoded default path.")

# Directory configuration
INPUT_DIR = "compiled_objects"
OUTPUT_DIR = "cfg_outputs"
GHIDRA_TEMP_PROJECT = "ghidra_temp_proj"
# SCRIPT_NAME = "extract_cfg_headless.py"
SCRIPT_NAME = "export_cfg_lta.py"


def run_ghidra_batch():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Verify Ghidra executable path
    if not os.path.exists(GHIDRA_PATH):
        print(f"ERROR: Ghidra executable not found. Check GHIDRA_PATH: {GHIDRA_PATH}")
        return

    # Collect all .o object files
    obj_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".o")]

    print(f"[*] Processing {len(obj_files)} object files...")
    print("="*50)

    for i, obj_file in enumerate(obj_files, 1):
        obj_path = os.path.abspath(os.path.join(INPUT_DIR, obj_file))
        out_path_abs = os.path.abspath(OUTPUT_DIR)

        print(f"[{i}/{len(obj_files)}] Analyzing: {obj_file}")

        # Build Ghidra Headless command
        # Format: analyzeHeadless <project_dir> <project_name> -import <target_file> -postScript <script> <script_args> -deleteProject
        cmd = [
            GHIDRA_PATH,
            os.path.abspath("."),       # temporary project directory
            GHIDRA_TEMP_PROJECT,        # temporary project name
            "-import", obj_path,        # .o file to import
            "-postScript", SCRIPT_NAME, # Jython script to run
            out_path_abs,               # first argument passed to Jython script (output directory)
            "-deleteProject",           # delete Ghidra project after analysis to save disk space
            "-overwrite"                # overwrite existing files
        ]

        try:
            # Suppress stdout; only surface stderr to keep output clean
            subprocess.run(cmd, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print(f"    [OK] CFG extracted successfully")
        except subprocess.CalledProcessError as e:
            print(f"    [FAIL] Extraction failed: {obj_file}")
            print(f"           Reason: {e.stderr.decode('utf-8', errors='ignore').strip()}")

    print("="*50)
    print(f"[*] Batch extraction complete. All CFGs saved to '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    run_ghidra_batch()
