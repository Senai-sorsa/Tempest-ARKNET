#!/bin/bash
# Autopilot: after the baseline diagnostics (IL-44), the per-year bias table (IL-19 evidence). Log data/ap_next.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
until grep -q "il44 done\|FAILED il44" data/ap_sh.log 2>/dev/null; do sleep 60; done
PYTHONPATH=. $PY -W ignore -u scripts/bias_by_year.py models/generator_80_p2f.pt models/generator_80_p2f.calib2021.npz data/train/pilot80_dpd.npz > data/ap_bias_by_year.log 2>&1 && echo "$(date '+%F %T') bias_by_year done" >> data/ap_next.log || echo "$(date '+%F %T') FAILED bias_by_year" >> data/ap_next.log
