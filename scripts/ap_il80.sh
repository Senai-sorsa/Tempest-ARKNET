#!/bin/bash
# IL-80 (capped loop 5/6): 50:50 mixture of the network and the ridge predictive samples for mode F, same evaluation as r1 (test 2022). Waits for IL-77. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
until grep -q "il77 done" data/ap_il77.log 2>/dev/null; do sleep 60; done
.venv/Scripts/python -W ignore -u scripts/il6_modeF.py --out models/modeF_r1.pt --width 128 --depth 2 --coarse 4 > data/il6_modeF_r1_blend.log 2>&1
echo "$(date '+%F %T') il80 done" >> data/ap_il80.log
