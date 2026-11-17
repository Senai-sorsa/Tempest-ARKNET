#!/bin/bash
# 22.V1 balloon templates: new_plan_kit/b71_v1_balloon_templates.py. Log: data/l3.log [V1], output data/v1.log, result docs/results/logs/kit_b71_v1_balloon_templates.log. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=8 PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [V1] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b71_v1_balloon_templates.py > data/v1.log 2>&1 && log "done" || log "FAILED"
