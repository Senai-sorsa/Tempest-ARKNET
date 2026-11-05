#!/bin/bash
# Autopilot IL-77: regularised mode F variants (CPU). Waits for the first mode F evaluation. Logs data/il6_modeF_r*.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
until grep -q "skill vs climatology by variable\|Traceback" data/il6_modeF.log 2>/dev/null; do sleep 60; done
$PY -W ignore -u scripts/il6_modeF.py --out models/modeF_r1.pt --width 128 --depth 2 --wd 1e-2 --lr 3e-4 --coarse 4 --steps 1500 --retrain > data/il6_modeF_r1.log 2>&1
$PY -W ignore -u scripts/il6_modeF.py --out models/modeF_r2.pt --width 64 --depth 2 --wd 1e-1 --lr 3e-4 --coarse 8 --noise-dim 8 --steps 1500 --retrain > data/il6_modeF_r2.log 2>&1
echo "$(date '+%F %T') modeF regularised variants done" >> data/ap_modeF2.log
