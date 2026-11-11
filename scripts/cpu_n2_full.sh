#!/bin/bash
# N2 full run (New_Plan 10.4): one Mode F network fit on HRES / ERA5 pairs at the 7,483 world points (no lat / lon), scored on each box's own
# 2022 test rows; arms: world as it is, world + 300 fine-tune steps on the box rows, the box's own model (as shipped, same seed). Seeds 0 and 1.
# ENSF2 HRES-only recipe throughout. One job at a time (Mode F evaluation peaks at 14-17 GB). Verdict: new_plan_kit/b5_modeF_world.py.
# Log: data/l3.log [N2F]; per-run logs data/n2f_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N2F] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n2f_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "start"
$PY -W ignore -u scripts/il6_build_world.py --years 2016-2020 --points 150 > data/n2f_build.log 2>&1 && log "world rows built" || { log "FAILED world rows"; exit 1; }
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run base$tag$sfx --rows-dir $rows $R --seed $S --out models/modeF_n2_base$tag$sfx.pt       # seed 0 .pt exists from step 0: evaluation only
    [ -n "$tag" ] && [ -f models/modeF_n2w_s$S.pt ] && cp models/modeF_n2w_s$S.pt models/modeF_n2w_den_s$S.pt
    run world$tag$sfx --rows-dir $rows --fit-rows-dir data/modeF_world --no-place $R --seed $S --out models/modeF_n2w${tag}_s$S.pt
    run ft$tag$sfx --rows-dir $rows --no-place --init models/modeF_n2w_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2ft${tag}_s$S.pt
  done
done
log done
