#!/usr/bin/env python3
import os
from pathlib import Path


def merge_directory(target_dir_name):
    dir_path = Path("reveal_results") / target_dir_name

    if not dir_path.exists() or not dir_path.is_dir():
        print(f"WARNING: Directory not found: {dir_path}")
        return

    # Output merged file saved within the same subdirectory
    output_file = dir_path / f"merged_{target_dir_name}.txt"

    # Collect all .cpp files sorted by filename (e.g., 0_O0.cpp, 0_O1.cpp, ...)
    cpp_files = sorted(dir_path.glob("*.cpp"))

    if not cpp_files:
        print(f"WARNING: No .cpp files found in {dir_path}.")
        return

    with open(output_file, "w", encoding="utf-8") as out_f:
        for filepath in cpp_files:
            filename = filepath.name

            out_f.write(f"---start of {filename}\n")

            try:
                content = filepath.read_text(encoding="utf-8")
                # Ensure trailing newline to avoid concatenation artifacts
                if not content.endswith("\n"):
                    content += "\n"
                out_f.write(content)
            except Exception as e:
                out_f.write(f"// Failed to read file: {e}\n")

            out_f.write(f"--- end of {filename}\n\n")

    print(f"[OK] Merged {len(cpp_files)} files into: {output_file}")


def main():
    print("[*] Starting C++ file merge...\n")
    directories = ["base", "dot", "lta"]

    for dir_name in directories:
        merge_directory(dir_name)

    print("\n[*] All directories merged.")


if __name__ == "__main__":
    main()
