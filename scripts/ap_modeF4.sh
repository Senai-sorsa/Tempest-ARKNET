#!/bin/bash
# Autopilot IL-82: Schaake shuffle for mode F (regularised network r1, no retraining). Waits for ap_modeF3. Log data/il6_modeF_r1_shuffle.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
until grep -q "modeF shape done" data/ap_modeF3.log 2>/dev/null; do sleep 60; done
.venv/Scripts/python -W ignore -u scripts/il6_modeF.py --out models/modeF_r1.pt --width 128 --depth 2 --coarse 4 > data/il6_modeF_r1_shuffle.log 2>&1
echo "$(date '+%F %T') modeF shuffle done" >> data/ap_modeF4.log
