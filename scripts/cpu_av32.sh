#!/bin/bash
# New_Plan 13 AV32: O3 launch-week factor from the IL-207b start, alpha 1/60, seeds 0 and 1 (CPU). Verdict in new_plan_kit/b41_av32_launch_week_slow.py (rule in its header).
# Launch: nohup bash scripts/cpu_av32.sh &  Log: data/l3.log [AV32]; run output data/av32.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV32] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b41_av32_launch_week_slow.py > data/av32.log 2>&1 && log done || log FAILED
