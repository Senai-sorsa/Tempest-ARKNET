#!/bin/bash
# New_Plan 28.8 step 3: AV19 Student-t noise (configs/s25/av19.toml) on the c4w paired-base recipe (steps 1-2 dropped, so the stack is the base),
# full s25 arm (train, maps, scores, shape, Denver) seeds 0 and 100 by scripts/s25_arm.sh. Rule: new_plan_kit/s25_judges.py av19s25 (written before the run).
# Waits for step 2's runner to finish (no interleaving), GPU < 85 C before each seed. Finished steps are kept by s25_arm.sh.
# Launch: nohup bash scripts/gpu_av19s25.sh > /dev/null 2>&1 &   Log: data/l3.log [AV19S25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV19S25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[AV34S25\] \(done\|FAILED\)" data/l3.log; do sleep 60; done
log start
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  bash scripts/s25_arm.sh av19s25 $S configs/s25/av19.toml && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py av19s25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
