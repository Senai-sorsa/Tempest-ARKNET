#!/bin/bash
# Autopilot group SH step 1 (IL-44): baseline shape diagnostics of the adopted model p2f. Waits for the S chain. Log data/ap_sh.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
until grep -q "group S done" data/ap_s.log 2>/dev/null; do sleep 60; done
PYTHONPATH=. $PY -W ignore -u scripts/diagnose.py models/generator_80_p2f.pt models/generator_80_p2f.calib2021.npz data/train/pilot80_dpd.npz --out models/generator_80_p2f_base > data/ap_il44.log 2>&1 && echo "$(date '+%F %T') il44 done" >> data/ap_sh.log || echo "$(date '+%F %T') FAILED il44" >> data/ap_sh.log
