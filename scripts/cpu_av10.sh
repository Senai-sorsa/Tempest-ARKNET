#!/bin/bash
# New_Plan 13 AV10: O3 launch-week factor from the IL-207b start, seeds 0 and 1 (CPU). Verdict in new_plan_kit/b38_av10_launch_week_il207b.py (rule in its header).
# Launch: nohup bash scripts/cpu_av10.sh &  Log: data/l3.log [AV10]; run output data/av10.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV10] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b38_av10_launch_week_il207b.py > data/av10.log 2>&1 && log done || log FAILED
