#!/bin/bash
# N4 (New_Plan 10.4): ENSF2 recipe (cpu_ensf2_seed1.sh) + --ens-mask 0.3 (ensemble inputs zeroed on 30 % of training rows, plus a present bit). Each network is evaluated twice:
# with the feed (models/modeF_ensmask*_eval.csv) and without it (--ens-absent -> *_noens_eval.csv). Both boxes, seeds 0 and 1. Verdict: new_plan_kit/b5_modeF_mask.py. Log: data/l3.log [N4].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N4] $*" >> data/l3.log; }
log start
for s in 0 1; do
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}; out=models/modeF_ensmask${tag}_s$s.pt
    C="--rows-dir $rows --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed $s --ens --ens-mask 0.3 --out $out"
    $PY -W ignore -u scripts/il6_modeF.py $C > data/n4_mask${tag}_s$s.log 2>&1 && log "feed$tag s$s done" || log "FAILED feed$tag s$s"
    $PY -W ignore -u scripts/il6_modeF.py $C --ens-absent > data/n4_mask${tag}_s${s}_noens.log 2>&1 && log "nofeed$tag s$s done" || log "FAILED nofeed$tag s$s"
  done
done
log done
