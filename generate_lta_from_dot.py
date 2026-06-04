import json
import re
import os


def convert_dot_to_lta(dot_content):
    if not dot_content or dot_content == "// DOT File Not Found":
        return "// LTA Generation Failed"

    lta_blocks = []

    # 1. Parse nodes (basic blocks)
    # Example match: "402569_13" [label="endbr64\lpush rbp\l..."]
    node_pattern = re.compile(r'"([^"]+)"\s*\[label="([^"]+)"', re.DOTALL)
    nodes = node_pattern.findall(dot_content)

    # 2. Parse edges (control flow)
    # Example match: "402569_13" -> "4025a4_6" [label="fake_return"]
    edge_pattern = re.compile(
        r'"([^"]+)"\s*->\s*"([^"]+)"\s*(?:\[label="?([^"\]]+)"?\])?')
    edges = edge_pattern.findall(dot_content)

    # Build a map of outgoing edges per node
    edge_map = {}
    for src, dest, label in edges:
        if src not in edge_map:
            edge_map[src] = []
        edge_map[src].append((dest, label or "NEXT"))

    # 3. Assemble LTA format
    for node_id, label in nodes:
        # Clean \l newline markers from label
        instructions = label.replace('\\l', '\n').strip()

        block_str = f"[BLOCK: {node_id}]\n"
        # Indent each instruction
        for line in instructions.split('\n'):
            if line.strip():
                block_str += f"  {line.strip()}\n"

        # Append control flow edges
        if node_id in edge_map:
            for dest, edge_label in edge_map[node_id]:
                # Normalize label to uppercase, e.g., -> JUMP: 402698
                formatted_label = edge_label.upper().replace(" ", "_")
                # dest may contain a count suffix; extract the address prefix only
                dest_addr = dest.split('_')[0]
                block_str += f"  -> {formatted_label}: {dest_addr}\n"

        lta_blocks.append(block_str)

    return "\n".join(lta_blocks)


def main(input_file="HumanEval-Decompile-cpp.jsonl", output_file="HumanEval-Decompile-cpp-LTA.jsonl"):
    print(f"[*] Converting DOT to LTA from {input_file}...")

    with open(input_file, "r", encoding="utf-8") as f_in, \
            open(output_file, "w", encoding="utf-8") as f_out:

        for line in f_in:
            if not line.strip():
                continue
            record = json.loads(line)

            # Convert and write back
            dot_content = record.get("cfg_dot", "")
            record["cfg_lta"] = convert_dot_to_lta(dot_content)

            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[*] Conversion complete. Output saved to: {output_file}")


if __name__ == "__main__":
    main()
