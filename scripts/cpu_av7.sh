#!/bin/bash
# New_Plan 13 AV7: O1 two neighbours, 600 h per target, seeds 2 and 3 (CPU). Verdict in new_plan_kit/b22_av7_two_neighbours.py (rule in its header).
# Launch: nohup bash scripts/cpu_av7.sh &  Log: data/l3.log [AV7]; run output data/av7.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV7] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b22_av7_two_neighbours.py > data/av7.log 2>&1 && log done || log FAILED
