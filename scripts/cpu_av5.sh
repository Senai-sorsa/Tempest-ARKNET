#!/bin/bash
# AV5 (New_Plan 13): third training seed (2) of the N2 arms, both boxes: own model, world network, world + 300 fine-tune steps, own + 300 control.
# Same recipe and order as scripts/cpu_n2_full.sh + scripts/cpu_n2_control.sh. Verdict: new_plan_kit/b16_av5_third_seed.py. Log: data/l3.log [AV5].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV5] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/av5_$name.log 2>&1 && log "$name done" || { log "FAILED $name"; exit 1; }; }
S=2
log "start"
for box in "modeF_ens:" "modeF_ens_denver:_den"; do
  rows=data/${box%%:*}; tag=${box##*:}
  run base$tag --rows-dir $rows $R --seed $S --out models/modeF_n2_base${tag}_s$S.pt
  [ -n "$tag" ] && cp models/modeF_n2w_s$S.pt models/modeF_n2w_den_s$S.pt
  run world$tag --rows-dir $rows --fit-rows-dir data/modeF_world --no-place $R --seed $S --out models/modeF_n2w${tag}_s$S.pt
  run ft$tag --rows-dir $rows --no-place --init models/modeF_n2w_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2ft${tag}_s$S.pt
  run own300$tag --rows-dir $rows --init models/modeF_n2_base${tag}_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2own300${tag}_s$S.pt
done
log done
