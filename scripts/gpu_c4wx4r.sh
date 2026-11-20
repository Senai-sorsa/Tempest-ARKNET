#!/bin/bash
# New_Plan 28.11 item 7 / 10: final-model climate candidate = shipped c4w (models/l3_c4w.pt) + X4-R, no retrain.
# Pre-set pick (written 2026-11-20 13:30, before the x4ers25 verdict): k = 3 (variant e) if x4ers25 is PASS, else k = 2 (variant d, user ruling).
# Then the shipped c4w alone (c4wref) and c4w + X4-R (c4wx4r) go through the same s25 arm pipeline (PRE=1: maps / calibration refit,
# score (a) / (b), shape, Denver report), seed 0, so the X4-R effect on the shipped network is measured like-for-like on the same rows.
# Launch: nohup bash scripts/gpu_c4wx4r.sh > /dev/null 2>&1 &   Log: data/l3.log [C4WX4R]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python D=models/s25 L=docs/results/logs
log() { echo "$(date '+%F %T') [C4WX4R] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
until grep -q "\[X4ERS25\] \(done\|FAILED\|skipped\)" data/l3.log; do sleep 60; done
grep -q "\[X4ERS25\] FAILED" data/l3.log && { log "x4ers25 FAILED, stop (tick decides)"; exit 1; }
if grep -q "VERDICT (pre-set rule): PASS" $L/kit_s25_x4ers25.log 2>/dev/null; then K=3; else K=2; fi
log "start: x4ers25 verdict -> k $K"
export S25_STACK=base
[ -f $D/c4wref_s0.pt ] || cp models/l3_c4w.pt $D/c4wref_s0.pt
M=$D/c4wx4r_s0.pt
while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
[ -f $M ] || { PYTHONPATH=".;scripts" $PY -W ignore -u scripts/x4r_build.py models/l3_c4w.pt $M.part --k $K > $L/s25_c4wx4r_s0_build.log 2>&1 && mv $M.part $M && log "built k $K"; } || { log "FAILED build"; exit 2; }
for A in c4wx4r c4wref; do
  while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
  PRE=1 bash scripts/s25_arm.sh $A 0 configs/s25/x4er.toml && log "$A done" || { log "FAILED $A"; exit 2; }
done
log done
