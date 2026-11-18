#!/bin/bash
cd /c/Users/Senai/Tempest-ARKNET
source scripts/cap_cpu.sh 2>/dev/null
for s in 0 1; do
  KIT_SEED=$s PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b79_w2_copula_uv.py > data/b79_s$s.out 2>&1
  cp docs/results/logs/kit_b79_w2_copula_uv.log data/b79_log_seed$s.txt
done
