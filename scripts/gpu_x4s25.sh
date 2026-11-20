#!/bin/bash
# New_Plan 28.9 (28.4 MISS-idea arm): X4 = climatology-mean anomaly output with RH plain (configs/s25/x4.toml) on top of the 28.3 stack:
# the base, or base + AV19 if new_plan_kit/s25_judges.py av19s25 gave PASS (then AV19's keys are stacked). Full s25 arm, seeds 0 and 100,
# Denver with the anomaly table refit on Denver rows <= 2020 (ANOM_DEN=1). Rule: s25_judges.py x4s25 (written before the run).
# Launch: nohup bash scripts/gpu_x4s25.sh > /dev/null 2>&1 &   Log: data/l3.log [X4S25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [X4S25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[AV19S25\] \(done\|FAILED\)" data/l3.log; do sleep 60; done
CFG=configs/s25/x4.toml STACK=base
if grep -q "VERDICT (pre-set rule): PASS" docs/results/logs/kit_s25_av19s25.log 2>/dev/null; then
  CFG=configs/s25/x4_on_av19.toml STACK=av19s25
  [ -f $CFG ] || cat configs/s25/av19.toml configs/s25/x4.toml > $CFG
fi
export S25_STACK=$STACK
log "start (stack $STACK, $CFG)"
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  ANOM_DEN=1 bash scripts/s25_arm.sh x4s25 $S $CFG && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py x4s25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
