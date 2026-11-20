#!/bin/bash
# New_Plan 28.10 step 2: X4 variant b (configs/s25/x4b.toml: v plain too, climatology offset x0.5) on the base stack (AV19 KILL), full s25 arm,
# seeds 0 and 100, Denver with the anomaly table refit on Denver rows <= 2020 (ANOM_DEN=1). Rule: s25_judges.py x4bs25 (written before the run).
# Launch: nohup bash scripts/gpu_x4bs25.sh > /dev/null 2>&1 &   Log: data/l3.log [X4BS25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [X4BS25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
export S25_STACK=base
log "start (stack base, configs/s25/x4b.toml)"
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  ANOM_DEN=1 bash scripts/s25_arm.sh x4bs25 $S configs/s25/x4b.toml && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py x4bs25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
