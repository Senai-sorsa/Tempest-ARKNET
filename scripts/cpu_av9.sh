#!/bin/bash
# New_Plan 13 AV9: O4 analog tail fix, upward shift only, odd / even test days (CPU, a few minutes). Verdict in new_plan_kit/b39_av9_analog_up_only.py (rule in its header).
# Launch: nohup bash scripts/cpu_av9.sh &  Log: data/l3.log [AV9]; run output data/av9.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit;scripts"
log() { echo "$(date '+%F %T') [AV9] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b39_av9_analog_up_only.py > data/av9.log 2>&1 && log done || log FAILED
