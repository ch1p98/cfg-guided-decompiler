# extract_cfg_headless.py
# STRICTLY NO NON-ASCII CHARACTERS IN THIS FILE (Jython 2.7 limitation)

import os
from ghidra.program.model.block import BasicBlockModel
from ghidra.util.task import TaskMonitor


def get_output_dir():
    # Retrieve arguments passed from the headless analyzer
    args = getScriptArgs()
    if len(args) > 0:
        return args[0]
    return "/tmp"


def export_cfg_to_dot(func, filepath):
    block_model = BasicBlockModel(currentProgram)
    monitor = TaskMonitor.DUMMY

    # Get all basic blocks for the function
    blocks = block_model.getCodeBlocksContaining(func.getBody(), monitor)

    with open(filepath, 'w') as f:
        f.write("digraph G {\n")

        while blocks.hasNext():
            block = blocks.next()
            block_addr = block.getFirstStartAddress().toString()
            f.write("  \"%s\" [label=\"%s\"];\n" % (block_addr, block_addr))

            destinations = block.getDestinations(monitor)
            while destinations.hasNext():
                dest_ref = destinations.next()
                dest_addr = dest_ref.getDestinationAddress().toString()

                # Check if the destination is within the function body
                if func.getBody().contains(dest_ref.getDestinationAddress()):
                    f.write("  \"%s\" -> \"%s\";\n" % (block_addr, dest_addr))

        f.write("}\n")


def main():
    output_dir = get_output_dir()

    # Ensure output directory exists (Jython compatible way)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get the program name (e.g., record_112_O0.o) to use as prefix
    prog_name = currentProgram.getName()
    base_name = prog_name.replace(".o", "")

    fm = currentProgram.getFunctionManager()
    funcs = fm.getFunctions(True)  # True means forward iteration

    for func in funcs:
        # We only care about the target functions, usually starting with 'func' or mangled names
        func_name = func.getName()
        if "func" in func_name or "_Z" in func_name:
            print("[+] Processing function: " + func_name)
            out_file = os.path.join(
                output_dir, base_name + "_" + func_name + ".dot")
            export_cfg_to_dot(func, out_file)


if __name__ == "__main__":
    main()
