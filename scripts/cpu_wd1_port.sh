#!/bin/bash
# New_Plan 28.11 item 12: wait for the WD1 table build (scripts/build_ur5.py on the shipped assets), then the tool-path rerun b89. Log: data/l3.log [WD1PORT]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [WD1PORT] $*" >> data/l3.log; }
until [ -f models/ur5_wd1_shipped.npz ] || grep -q "Error" docs/results/logs/build_ur5_shipped.log; do sleep 30; done
[ -f models/ur5_wd1_shipped.npz ] || { log "FAILED build"; exit 1; }
log "table built: $(tail -1 docs/results/logs/build_ur5_shipped.log)"
PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore -u new_plan_kit/b89_wd1_tool_path.py models/ur5_wd1_shipped.npz > docs/results/logs/b89_run.log 2>&1 && log done || log "FAILED b89"
