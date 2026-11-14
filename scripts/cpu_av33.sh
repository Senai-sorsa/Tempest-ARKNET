#!/bin/bash
# New_Plan 13 AV33: O3 launch-week factor from the IL-207b start, alpha 1/60, seeds 0 and 1 (CPU), 300 test days per site; run ALONE (two 16-thread jobs starve each other). Verdict in new_plan_kit/b43_av33_launch_week_300d.py (rule in its header).
# Launch: nohup bash scripts/cpu_av33.sh &  Log: data/l3.log [AV33]; run output data/av33.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=".;new_plan_kit"
log() { echo "$(date '+%F %T') [AV33] $*" >> data/l3.log; }
log start
.venv/Scripts/python -W ignore -u new_plan_kit/b43_av33_launch_week_300d.py > data/av33.log 2>&1 && log done || log FAILED
