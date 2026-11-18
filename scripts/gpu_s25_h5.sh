#!/bin/bash
# New_Plan 25 H5: draft + refine. Per seed: train the refine flows (t0 0.2 / 0.4 = tau_min 0.8 / 0.6, 3 Euler steps) as h5_t02f / h5_t04f
# (STAGE=train), compose each with the paired base_s{seed} as the frozen draft (scripts/s25_compose_refine.py, member k with member k)
# -> h5_t02 / h5_t04, then the full pipeline on the composed model (PRE=1). Judge h5.
#   nohup bash scripts/gpu_s25_h5.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_h5.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do for t in t02 t04; do
  STAGE=train bash scripts/s25_arm.sh h5_${t}f $s configs/s25/h5_$t.toml || exit 2
  O=models/s25/h5_${t}_s$s.pt
  if [ ! -e $O ]; then
    if [ "$DRY" = "1" ]; then echo "compose models/s25/base_s$s.pt + models/s25/h5_${t}f_s$s.pt -> $O"; else
      . scripts/cap_cpu.sh
      env PYTHONPATH=. .venv/Scripts/python -W ignore scripts/s25_compose_refine.py --draft models/s25/base_s$s.pt --flow models/s25/h5_${t}f_s$s.pt --out $O \
        > docs/results/logs/s25_h5_${t}_s${s}_compose.log 2>&1 || { echo "$(date "+%F %T") [S25 h5] FAILED compose $O" >> docs/results/logs/s25.log; exit 2; }
    fi
  fi
  [ "$DRY" = "1" ] && [ ! -e $O ] && { echo "full pipeline (PRE=1) on $O"; continue; }
  PRE=1 bash scripts/s25_arm.sh h5_$t $s configs/s25/h5_$t.toml || exit 2
done; done
JUDGE h5
