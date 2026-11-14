#!/bin/bash
# New_Plan 13 AV31: S1 map then update, 120 prior h per cell, ONM/FST/ABQ left out, seeds 0 and 1 (CPU). Verdict in new_plan_kit/b42_av31_map_then_update_600h.py (rule in its header).
# Launch: nohup bash scripts/cpu_av31.sh &  Log: data/l3.log [AV31]; run output data/av31.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV31] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b42_av31_map_then_update_600h.py > data/av31.log 2>&1 && log done || log FAILED
