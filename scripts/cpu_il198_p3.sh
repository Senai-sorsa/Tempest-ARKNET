#!/bin/bash
# IL-198 (CPU): rerun scripts/p3_vad_condition.py (EPZ radar vs the 00Z balloon, 120 days 2021-23) with --per-day so the radar gain can be given an interval (date-block bootstrap, scripts/il198_bootstrap.py).
# Exact command: PYTHONPATH=. .venv/Scripts/python -W ignore -u scripts/p3_vad_condition.py --n 120 --per-day data/il198_p3_perday.csv > data/il198_p3.log
# Log: data/l3.log [IL198P3]. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
log() { echo "$(date '+%F %T') [IL198P3] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u scripts/p3_vad_condition.py --n 120 --per-day data/il198_p3_perday.csv > data/il198_p3.log 2>&1 && log "done" || log "FAILED"
