#!/bin/bash
# SIGMA stage 2 (New_Plan 14.3, 13.5 step 3): Mode F at the shipped size on all leads to 10 d, target (truth - base) / s (il6_modeF.py --sigma,
# tempest/forecast/sigma.py). Same recipe, rows and test rows as N5 (scripts/cpu_n5_full.sh), --sigma in place of --fit-beyond, so the N5 binned
# models modeF_n5_bin{,_den}_s{0,1} are the reference as they stand. Seeds 0 and 1, both boxes, one job at a time (evaluation peaks at 14-17 GB).
# Verdict: new_plan_kit/b18_sigma_stage2.py. Log: data/l3.log [SIG2]; per-run logs data/sig2_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [SIG2] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --retrain"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/sig2_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "start"
for S in 0 1; do
  for box in "modeF_v2:" "modeF_v2_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run sig${tag}_s$S --rows-dir $rows $R --seed $S --out models/modeF_n5_sig${tag}_s$S.pt
  done
done
log done
