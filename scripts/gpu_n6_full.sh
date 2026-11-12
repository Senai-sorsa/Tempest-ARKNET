#!/bin/bash
# N6 full run (New_Plan 10.4; step 0 PASSED 2026-11-11 23:06, validation 0.4986 at step 250 -> 0.4787 at step 2750):
# full-size Mode F (width 512, depth 4, 4 members, --coarse 1, no lat / lon) = world fit (models/modeF_n6w_s$S.pt) + 300 steps on the box rows.
# Compared with the small own-box model on the same test rows: models/modeF_n2_base{,_den}{,_s1} (N2). Verdict: new_plan_kit/b5_modeF_big.py.
# World seed 1 fit runs at once (GPU, --fit-only, ~3 min, no evaluation); the fine-tunes evaluate (14-17 GB RAM), so they wait for [N2B] done.
# Launch: powershell Start-Process bash.exe scripts/gpu_n6_full.sh (detached). Log: data/l3.log [N6F]; per-run data/n6f_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=4 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N6F] $*" >> data/l3.log; }
R="--no-place --width 512 --depth 4 --coarse 1 --members 4 --lr 3e-4 --wd 1e-2 --device cuda"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n6f_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "start"
run world_s1 --rows-dir data/modeF_ens --fit-rows-dir data/modeF_world $R --steps 3000 --seed 1 --fit-only --out models/modeF_n6w_s1.pt
log "waiting for N2B"
until grep -qE "\[N2B\] done$" data/l3.log; do sleep 60; done
for S in 0 1; do
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run ft${tag}_s$S --rows-dir $rows --init models/modeF_n6w_s$S.pt --retrain $R --steps 300 --save-rows --seed $S --out models/modeF_n6ft${tag}_s$S.pt
  done
done
log done
