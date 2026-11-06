#!/bin/bash
# IL-77 (capped loop 3/6): mode F with the regularised settings of r1 but 4 members (variance of the seed ensemble) and 2500 steps; same evaluation as r1/v2 (test 2022). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
.venv/Scripts/python -W ignore -u scripts/il6_modeF.py --out models/modeF_r3.pt --width 128 --depth 2 --wd 1e-2 --lr 3e-4 --coarse 4 --steps 2500 --members 4 --retrain > data/il6_modeF_r3.log 2>&1
echo "$(date '+%F %T') il77 done" >> data/ap_il77.log
