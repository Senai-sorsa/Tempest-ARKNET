#!/bin/bash
# N2 control (user 2026-11-11 17:30 "Run N2"): the box's own model + 300 more steps on its own rows (same recipe and seed as the N2 fine-tune arm),
# so the world-then-box gain can be told apart from the extra training. Waits for the N5 runner (one Mode F job at a time, evaluation 14-17 GB).
# Out: models/modeF_n2own300{,_den}_s{0,1}; verdict: new_plan_kit/b5_modeF_world.py (adds the control when present). Log: data/l3.log [N2C].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N2C] $*" >> data/l3.log; }
log "waiting for N5"
until grep -qE "\[N5F\] done$" data/l3.log; do sleep 60; done
R="--width 128 --depth 2 --coarse 4 --steps 300 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --retrain"
log "start"
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}; name=own300${tag}_s$S
    $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows --init models/modeF_n2_base$tag$sfx.pt $R --seed $S --out models/modeF_n2own300${tag}_s$S.pt > data/n2c_$name.log 2>&1 && log "$name done" || log "FAILED $name"
  done
done
log done
