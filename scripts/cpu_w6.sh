#!/bin/bash
cd /c/Users/Senai/Tempest-ARKNET
source scripts/cap_cpu.sh 2>/dev/null
for s in 0 1; do
  W1_NOSHRINK=1 W1_TAPER=1 KIT_SEED=$s PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b81_w1_shear_stretch.py > data/b81w6_s$s.out 2>&1
  cp docs/results/logs/kit_b81_w1_shear_stretch_w5_w6.log data/b81w6_log_seed$s.txt
done
