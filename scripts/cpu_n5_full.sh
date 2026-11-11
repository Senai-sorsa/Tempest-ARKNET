#!/bin/bash
# N5 full run (New_Plan 10.4): one Mode F network from day 1 to climate. Rows: data/modeF_v2{,_denver} (the only stores with leads 7.5-10 d).
# Both arms load and score the same rows, leads binned 1 / 3 / 5 / 7 plus 9 (= beyond 7.5 d), --all-leads:
#   binned  models/modeF_n5_bin{,_den}_s$S   network fit on leads <= 7.5 d only (as shipped; at bin 9 it is used beyond its range)
#   all     models/modeF_n5_all{,_den}_s$S   network fit on all leads + 10 % climate-anchor rows (--fit-beyond)
# ENSF2 HRES-only recipe, seeds 0 and 1, one job at a time (evaluation peaks at 14-17 GB). Verdict: new_plan_kit/b5_modeF_alllead.py.
# Log: data/l3.log [N5F]; per-run logs data/n5f_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N5F] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n5f_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "start"
for S in 0 1; do
  for box in "modeF_v2:" "modeF_v2_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run bin${tag}_s$S --rows-dir $rows $R --seed $S --out models/modeF_n5_bin${tag}_s$S.pt
    run all${tag}_s$S --rows-dir $rows $R --fit-beyond --seed $S --out models/modeF_n5_all${tag}_s$S.pt
  done
done
log done
