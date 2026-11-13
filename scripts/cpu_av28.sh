#!/bin/bash
# AV28 (New_Plan 13): N2 world-start fine-tune with 500 steps instead of 300, against the own model + 500 steps (the matching control),
# seeds 0 / 1 / 2, both boxes. Reuses the AV5 / N2 world networks (models/modeF_n2w_s{S}.pt) and own models. Verdict: new_plan_kit/b17_av28_ft500.py.
# Log: data/l3.log [AV28]; per-run logs data/av28_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV28] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --retrain"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/av28_$name.log 2>&1 && log "$name done" || { log "FAILED $name"; exit 1; }; }
log "start"
for S in 0 1 2; do
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    own=models/modeF_n2_base$tag$([ $S = 0 ] && echo "" || echo "_s$S").pt
    [ -f $own ] && [ -f models/modeF_n2w_s$S.pt ] || { log "FAILED missing start network s$S$tag"; exit 1; }
    run ft500${tag}_s$S --rows-dir $rows --no-place --init models/modeF_n2w_s$S.pt $R --seed $S --out models/modeF_n2ft500${tag}_s$S.pt
    run own500${tag}_s$S --rows-dir $rows --init $own $R --seed $S --out models/modeF_n2own500${tag}_s$S.pt
  done
done
log done
