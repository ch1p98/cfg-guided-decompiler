# export_cfg_lta.py
# =======================================================================
# STRICTLY ASCII ONLY. DO NOT ADD CHINESE CHARACTERS OR FULL-WIDTH SYMBOLS.
# Jython 2.7 will crash if it encounters non-ASCII characters.
# =======================================================================

import os
from ghidra.program.model.block import BasicBlockModel
from ghidra.util.task import TaskMonitor


def get_output_dir():
    # Retrieve the output directory path passed from batch_run_ghidra.py
    args = getScriptArgs()
    if len(args) > 0:
        return args[0]
    return "."


def process_function(func, out_dir, base_name):
    func_name = func.getName()

    # Only process targets (e.g., "func0" or mangled C++ names starting with "_Z")
    if not ("func" in func_name or "_Z" in func_name):
        return

    print("[+] Exporting LTA for: " + func_name)

    # Construct filename: e.g., record_112_O0_func0.lta
    file_name = base_name + "_" + func_name + ".lta"
    file_path = os.path.join(out_dir, file_name)

    block_model = BasicBlockModel(currentProgram)
    monitor = TaskMonitor.DUMMY
    blocks = block_model.getCodeBlocksContaining(func.getBody(), monitor)
    listing = currentProgram.getListing()

    with open(file_path, "w") as f:
        while blocks.hasNext():
            block = blocks.next()
            start_addr = block.getFirstStartAddress().toString()

            # Print Block Header
            f.write("[BLOCK: " + start_addr + "]\n")

            # Iterate instructions within the block
            ins_iter = listing.getInstructions(block, True)
            while ins_iter.hasNext():
                ins = ins_iter.next()
                addr_str = ins.getAddress().toString()
                ins_str = ins.toString()
                f.write("  " + addr_str + " " + ins_str + "\n")

            # Iterate outgoing edges (Control Flow)
            dests = block.getDestinations(monitor)
            while dests.hasNext():
                dest = dests.next()
                dest_addr = dest.getDestinationAddress().toString()
                flow_type = dest.getFlowType().toString()

                # Format the flow type to match your LTA Prompt style
                # e.g., "UNCONDITIONAL CALL", "CONDITIONAL JUMP"
                edge_label = flow_type.upper().replace(" ", "_")
                f.write("  -> " + edge_label + ": " + dest_addr + "\n")

            f.write("\n")


def main():
    out_dir = get_output_dir()

    # Ensure the output directory exists
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Extract the original object filename without extension
    prog_name = currentProgram.getName()
    base_name = prog_name.replace(".o", "")

    fm = currentProgram.getFunctionManager()
    funcs = fm.getFunctions(True)

    for func in funcs:
        process_function(func, out_dir, base_name)


if __name__ == "__main__":
    main()
