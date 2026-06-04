#!/bin/bash

for mode in base dot lta; do
    echo "========================================"
    echo "[*] Evaluating mode: $mode"
    echo "========================================"
    python evaluate_reveal.py \
        --dataset test-cpp-LTA.jsonl \
        --outputs ablation_results/outputs_${mode}.jsonl
    echo ""
done
