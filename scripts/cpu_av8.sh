#!/bin/bash
# New_Plan 13 AV8: S1 map then update, 120 prior h per cell, ONM/FST/ABQ left out, seeds 0 and 1 (CPU). Verdict in new_plan_kit/b23_av8_map_then_update.py (rule in its header).
# Launch: nohup bash scripts/cpu_av8.sh &  Log: data/l3.log [AV8]; run output data/av8.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV8] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b23_av8_map_then_update.py > data/av8.log 2>&1 && log done || log FAILED
