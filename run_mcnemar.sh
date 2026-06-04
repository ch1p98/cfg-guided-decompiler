#!/bin/bash

echo "========================================"
echo "[*] Running McNemar's Test statistical analysis"
echo "========================================"

python evaluate_mcnemar.py \
    --dataset test-cpp-LTA.jsonl \
    --base ablation_results/outputs_base.jsonl \
    --dot ablation_results/outputs_dot.jsonl \
    --lta ablation_results/outputs_lta.jsonl

echo "========================================"
echo "[*] Statistical analysis complete."
echo "========================================"
