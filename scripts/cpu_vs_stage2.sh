#!/bin/bash
# VS stage 2 (CPU, kNN stand-in): new_plan_kit/b69_vs_stage2.py, 2 seeds. Log: data/l3.log [VS2], result docs/results/logs/kit_b69_vs_stage2.log. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=8 PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [VS2] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b69_vs_stage2.py > data/vs2.log 2>&1 && log "done" || log "FAILED"
