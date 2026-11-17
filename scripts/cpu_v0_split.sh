#!/bin/bash
# 22.V0 error split: new_plan_kit/b70_v0_split.py. Log: data/l3.log [V0], output data/v0.log, result docs/results/logs/kit_b70_v0_split.log. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=8 PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [V0] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b70_v0_split.py > data/v0.log 2>&1 && log "done" || log "FAILED"
