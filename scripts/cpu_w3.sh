#!/bin/bash
cd /c/Users/Senai/Tempest-ARKNET
source scripts/cap_cpu.sh 2>/dev/null
for s in 0 1; do
  KIT_SEED=$s PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b80_w3_shear_fade.py > data/b80_s$s.out 2>&1
  cp docs/results/logs/kit_b80_w3_shear_fade.log data/b80_log_seed$s.txt
done
