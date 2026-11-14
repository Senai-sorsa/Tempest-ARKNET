#!/bin/bash
# New_Plan 13 AV11: A2 past-mode spread x1.2 at the airports only (CPU, ~1-2 h). Verdict in new_plan_kit/b40_av11_airport_spread.py (rule in its header).
# Launch: nohup bash scripts/cpu_av11.sh &  Log: data/l3.log [AV11]; run output data/av11.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit;scripts"
log() { echo "$(date '+%F %T') [AV11] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b40_av11_airport_spread.py > data/av11.log 2>&1 && log done || log FAILED
