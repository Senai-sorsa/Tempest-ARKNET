#!/bin/bash
# N2 modification B (user 2026-11-11 17:30, "is there any way to slightly modify the idea"): data-scarce box. Only 1 fit year on the box (--fit-years 1);
# does the world start help when the box has little data? Arms per box x seed (ENSF2 HRES-only recipe, same test rows as N2):
#   own1      box's own model on 1 fit year (1500 steps)
#   own1p300  own1 + 300 more steps on the same rows (control for extra training)
#   ft1       world network (models/modeF_n2w_s$S.pt, no lat / lon) + 300 steps on the 1-year box rows
# Waits for the N2 control (one Mode F job at a time). Verdict: new_plan_kit/b5_modeF_scarce.py. Log: data/l3.log [N2B]; per-run data/n2b_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N2B] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --fit-years 1"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n2b_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "waiting for N2 control"
until grep -qE "\[N2C\] done$" data/l3.log; do sleep 60; done
log "start"
for S in 0 1; do
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run own1${tag}_s$S --rows-dir $rows $R --seed $S --out models/modeF_n2b_own1${tag}_s$S.pt
    run own1p300${tag}_s$S --rows-dir $rows --init models/modeF_n2b_own1${tag}_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2b_own1p300${tag}_s$S.pt
    run ft1${tag}_s$S --rows-dir $rows --no-place --init models/modeF_n2w_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2b_ft1${tag}_s$S.pt
  done
done
log done
