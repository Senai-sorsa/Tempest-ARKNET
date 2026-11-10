#!/bin/bash
# A1 step 2 (CPU): rerun scripts/w6_observe_eval.py with --per-hour so the observe-vs-persistence gap can be bootstrapped over days (same 300 hours per station, default rng).
# Exact command: PYTHONPATH=. .venv/Scripts/python -W ignore -u scripts/w6_observe_eval.py --n 300 --out docs/results/logs/a1_w6_rerun.log --per-hour data/a1_perhour.csv
# Log: data/l3.log [A1PH]. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
log() { echo "$(date '+%F %T') [A1PH] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u scripts/w6_observe_eval.py --n 300 --out docs/results/logs/a1_w6_rerun.log --per-hour data/a1_perhour.csv > data/a1_perhour.log 2>&1 && log "done" || log "FAILED"
