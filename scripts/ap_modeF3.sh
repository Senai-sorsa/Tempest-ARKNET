#!/bin/bash
# Autopilot IL-81: shape metrics for the first mode F network (no retraining). Waits for the regularised variants. Log data/il6_modeF_shape.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
until grep -q "regularised variants done" data/ap_modeF2.log 2>/dev/null; do sleep 60; done
.venv/Scripts/python -W ignore -u scripts/il6_modeF.py --out models/modeF.pt > data/il6_modeF_shape.log 2>&1
echo "$(date '+%F %T') modeF shape done" >> data/ap_modeF3.log
