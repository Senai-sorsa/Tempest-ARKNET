#!/bin/bash
# 22.V6 GRAM-like stand-in: new_plan_kit/b9_gram_compare.py --standin --gramlike --bank. Log: data/l3.log [V6], result docs/results/logs/kit_b9_gram_compare.log. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=8 PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [V6] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b9_gram_compare.py --standin --gramlike --bank > data/v6.log 2>&1 && log "done" || log "FAILED"
