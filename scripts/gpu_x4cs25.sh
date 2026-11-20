#!/bin/bash
# New_Plan 28.10 step 2: X4 variant c (configs/s25/x4c.toml: RH, v, rh2m plain, climatology offset x0.25), only if x4bs25 is KILL, on the base stack (AV19 KILL), full s25 arm,
# seeds 0 and 100, Denver with the anomaly table refit on Denver rows <= 2020 (ANOM_DEN=1). Rule: s25_judges.py x4cs25 (written before the run).
# Launch: nohup bash scripts/gpu_x4cs25.sh > /dev/null 2>&1 &   Log: data/l3.log [X4CS25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [X4CS25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[X4BS25\] \(done\|FAILED\)" data/l3.log; do sleep 60; done
grep -q "VERDICT (pre-set rule): KILL" docs/results/logs/kit_s25_x4bs25.log 2>/dev/null || { log "skipped (x4bs25 not KILL)"; exit 0; }
export S25_STACK=base
log "start (stack base, configs/s25/x4c.toml)"
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  ANOM_DEN=1 bash scripts/s25_arm.sh x4cs25 $S configs/s25/x4c.toml && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py x4cs25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
