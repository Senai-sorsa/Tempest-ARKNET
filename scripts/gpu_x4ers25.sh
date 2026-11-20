#!/bin/bash
# New_Plan 28.10 variant e, X4-R k = 3 (no retrain): only if x4rs25 is not PASS. x4rs25 s0 missed only on preclip (+0.000503 vs 0.0005, RH 5-18 km)
# from the small NM/TX harmonics left at k = 2; k = 3 (probe: NM/TX kept 0.004, Denver ~74 % of the full gain) keeps NM/TX ~ the base.
# Same arm (PRE=1, maps / calibration refit, Denver report on the same file). Rule: s25_judges.py x4ers25.
# Launch: nohup bash scripts/gpu_x4ers25.sh > /dev/null 2>&1 &   Log: data/l3.log [X4ERS25]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python D=models/s25 L=docs/results/logs
log() { echo "$(date '+%F %T') [X4ERS25] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[X4RS25\] \(done\|FAILED\)" data/l3.log; do sleep 60; done
grep -q "VERDICT (pre-set rule): PASS" $L/kit_s25_x4rs25.log 2>/dev/null && { log "skipped (x4rs25 PASS)"; exit 0; }
export S25_STACK=base
log start
for S in 0 100; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  M=$D/x4ers25_s$S.pt
  [ -f $M ] || { PYTHONPATH=".;scripts" $PY -W ignore -u scripts/x4r_build.py $D/base_s$S.pt $M.part --k 3 > $L/s25_x4ers25_s${S}_build.log 2>&1 && mv $M.part $M && log "s$S built"; } || { log "FAILED build s$S"; exit 2; }
  PRE=1 bash scripts/s25_arm.sh x4ers25 $S configs/s25/x4er.toml && log "s$S done" || { log "FAILED s$S"; exit 2; }
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py x4ers25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
