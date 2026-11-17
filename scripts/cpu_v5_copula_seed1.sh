#!/bin/bash
# 22.V5 copula templates: new_plan_kit/b71_v1_balloon_templates.py. Log: data/l3.log [V5s1], output data/v5s1.log, result docs/results/logs/kit_b71_v1_balloon_templates.log. Never two copies at once.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export KIT_SEED=1 OMP_NUM_THREADS=8 PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [V5s1] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b71_v1_balloon_templates.py --copula > data/v5s1.log 2>&1 && log "done" || log "FAILED"
