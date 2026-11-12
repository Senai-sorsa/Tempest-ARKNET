#!/bin/bash
# N2 modification C (New_Plan 10.4): the world Mode F network with 12 climate descriptors per grid point instead of lat / lon
# (il6_modeF.py --place-clim --no-place). Arms per box and seed: world-C as it is, world-C + 300 fine-tune steps on the box rows; compared with
# the N2 runs already on disk (own model, world, fine-tuned). Same recipe and rows as scripts/cpu_n2_full.sh. 8 runs, about 1 h.
# Waits for "[N1] done" (N1 scoring holds 11-14 GB RAM; one Mode F job at a time). Verdict: new_plan_kit/b5_modeF_place.py.
# Launch: powershell Start-Process bash.exe scripts/cpu_n2c_place.sh (detached). Log: data/l3.log [N2P]; per-run logs data/n2p_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N2P] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --no-place --place-clim"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n2p_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "waiting for N1"
until grep -qE "\[N1\] done$" data/l3.log; do sleep 60; done
log "start"
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    [ -n "$tag" ] && [ -f models/modeF_n2cw_s$S.pt ] && cp models/modeF_n2cw_s$S.pt models/modeF_n2cw_den_s$S.pt   # one world fit per seed; shortcut: its table holds the NM/TX box points, the Denver run adds its own at load
    run world$tag$sfx --rows-dir $rows --fit-rows-dir data/modeF_world $R --seed $S --out models/modeF_n2cw${tag}_s$S.pt
    run ft$tag$sfx --rows-dir $rows --init models/modeF_n2cw_s$S.pt --retrain ${R/--steps 1500/--steps 300} --seed $S --out models/modeF_n2cft${tag}_s$S.pt
  done
done
log done
