#!/bin/bash
# New_Plan 28.10 variant d, X4-R (no retrain): only if x4cs25 is not PASS. Per seed: scripts/x4r_build.py adds the residual-referenced
# climatology offset (k = 2, tables from rows <= 2020 of NM/TX and Denver) to models/s25/base_s<S>.pt, then the s25 arm with PRE=1
# (range calibration, shear / lapse maps refit, score a / b, shape, Denver report on the same file; no table swap). Rule: s25_judges.py x4rs25.
# Launch: nohup bash scripts/gpu_x4rs25.sh > /dev/null 2>&1 &   Log: data/l3.log [X4RS25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python D=models/s25 L=docs/results/logs
log() { echo "$(date '+%F %T') [X4RS25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[X4CS25\] \(done\|FAILED\)" data/l3.log; do sleep 60; done
grep -q "VERDICT (pre-set rule): PASS" $L/kit_s25_x4cs25.log 2>/dev/null && { log "skipped (x4cs25 PASS)"; exit 0; }
export S25_STACK=base
log start
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  M=$D/x4rs25_s$S.pt
  [ -f $M ] || { PYTHONPATH=".;scripts" $PY -W ignore -u scripts/x4r_build.py $D/base_s$S.pt $M.part --k 2 > $L/s25_x4rs25_s${S}_build.log 2>&1 && mv $M.part $M && log "s$S built"; } || { log "FAILED build s$S"; exit 2; }
  PRE=1 bash scripts/s25_arm.sh x4rs25 $S configs/s25/x4r.toml && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py x4rs25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
