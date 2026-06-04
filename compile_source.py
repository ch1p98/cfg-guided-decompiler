import json
import os
import subprocess


def compile_dataset_sources(input_file="test_sample_20.jsonl", output_dir="compiled_objects"):
    """
    Extract C++ source code from the dataset and compile each entry into an object file (.o).
    Compilation errors are caught and reported with detailed messages.
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    fail_count = 0

    print(f"[*] Reading {input_file} and starting compilation...\n" + "="*50)

    with open(input_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"ERROR: JSON parse error at line {line_num}, skipping.")
                continue

            # Extract required fields
            idx = record.get("index", "unknown")
            opt_level = record.get("opt", "O0")  # default to O0
            func_dep = record.get("func_dep", "")
            func_code = record.get("func", "")

            # 1. Assemble the full C++ translation unit.
            # func_dep may or may not include #include directives;
            # concatenating func_dep and func produces a self-contained compilable file.
            full_cpp_code = f"{func_dep}\n\n{func_code}"

            # Define temporary source and target object file paths
            cpp_filename = os.path.join(output_dir, f"temp_source_{idx}.cpp")
            obj_filename = os.path.join(output_dir, f"record_{idx}_{opt_level}.o")

            # 2. Write the assembled source to a temporary file
            with open(cpp_filename, "w", encoding="utf-8") as cpp_file:
                cpp_file.write(full_cpp_code)

            # 3. Build the compile command
            # -std=c++17: dataset standard
            # -c: compile only (do not link; no main required)
            # -O...: optimization level from the dataset record
            compile_cmd = [
                "g++",
                "-std=c++17",
                f"-{opt_level}",
                "-c", cpp_filename,
                "-o", obj_filename
            ]

            # 4. Run compilation and catch errors
            try:
                # capture_output=True intercepts stdout/stderr for controlled reporting
                result = subprocess.run(
                    compile_cmd, check=True, capture_output=True, text=True)
                print(f"[OK]   Index: {idx:3} | Opt: {opt_level:2} | Output: {obj_filename}")
                success_count += 1

            except subprocess.CalledProcessError as e:
                print(f"[FAIL] Index: {idx:3} | Opt: {opt_level:2}")
                print(f"       GCC error:\n{e.stderr.strip()}")
                print("-" * 50)
                fail_count += 1

            finally:
                # 5. Clean up the temporary .cpp file regardless of compile result
                if os.path.exists(cpp_filename):
                    os.remove(cpp_filename)

    # Summary report
    print("="*50)
    print(f"[*] Batch compilation complete.")
    print(f"    Succeeded: {success_count}")
    print(f"    Failed:    {fail_count}")
    print(f"[*] Output .o files saved to '{output_dir}'.")


# Entry point
compile_dataset_sources()
