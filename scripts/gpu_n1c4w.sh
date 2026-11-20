#!/bin/bash
# New_Plan 28.8 step 1: N1 cross-fitted members rebuilt on the c4w paired base recipe (configs/s25/gen/base_s{0,100}.toml, A21 rows 1991-2023),
# then the s25 stack: the N1 range map (fit on each member's held-out years) stands in as the arm's calib2021 file, shear and lapse maps refit
# in order on it, scores (a) / (b), shape and Denver report by scripts/s25_arm.sh (PRE=1: never retrains). Compared against models/s25/base_s{0,100}.
# shortcut: the N1 range map comes from 2008-23 held-out rows, the base's from 2021-23; that is N1's own recipe (b5 verdict), kept as is.
# Training waits for GPU < 85 C before each seed; n1_crossfit.py waits for 10 GB free RAM before each fold. Finished folds / steps are kept.
# Launch: nohup bash scripts/gpu_n1c4w.sh > /dev/null 2>&1 &   Log: data/l3.log [N1C4W]; training logs data/n1c4w_train_s<S>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=4 PYTHONPATH=.
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz
log() { echo "$(date '+%F %T') [N1C4W] $*" >> data/l3.log; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
log start
for S in 0 100; do
  M=models/s25/n1c4w_s$S.pt
  if [ ! -f models/s25/n1c4w_s$S.calibcf.npz ]; then
    while [ "$(gpu_c)" -ge 85 ]; do sleep 60; done
    $PY -W ignore -u scripts/n1_crossfit.py --seed $S --config configs/s25/gen/base_s$S.toml --data $A21 --out $M >> data/n1c4w_train_s$S.log 2>&1 \
      && log "trained s$S" || { log "FAILED train s$S"; exit 2; }
  fi
  [ -f models/s25/n1c4w_s$S.calib2021.npz ] || cp models/s25/n1c4w_s$S.calibcf.npz models/s25/n1c4w_s$S.calib2021.npz
  PRE=1 bash scripts/s25_arm.sh n1c4w $S configs/s25/base.toml && log "stack s$S done" || { log "FAILED stack s$S"; exit 2; }
done
log done
