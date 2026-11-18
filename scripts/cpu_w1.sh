#!/bin/bash
cd /c/Users/Senai/Tempest-ARKNET
source scripts/cap_cpu.sh 2>/dev/null
for s in 0 1; do
  KIT_SEED=$s PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b81_w1_shear_stretch.py > data/b81_s$s.out 2>&1
  cp docs/results/logs/kit_b81_w1_shear_stretch.log data/b81_log_seed$s.txt
done
