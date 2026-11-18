#!/bin/bash
# New_Plan 25 GT2: IL-8b token model (configs/s25/gt2_il8b.toml: il8 config, d 96, 3000 steps) trained on seeds 0 and 100, then the IL-23
# pool (scripts/s25_pool.py: the paired base's 4 MLP members + the 4 token members in one file), full pipeline on the pool, against the
# paired base (seeds 0 and 100). Judge gt2 (rule in its docstring). Cost: IL-8 ran ~1700 s per 500 steps, so ~3 h per seed.
#   nohup bash scripts/gpu_s25_gt2.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_gt2.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python D=models/s25
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do
  STAGE=train bash scripts/s25_arm.sh gt2_il8b $s configs/s25/gt2_il8b.toml || exit 2
  if [ ! -f $D/gt2_pool_s$s.pt ]; then
    if [ "$DRY" = "1" ]; then echo "pool $D/base_s$s.pt + $D/gt2_il8b_s$s.pt -> $D/gt2_pool_s$s.pt"; else
      $PY scripts/s25_pool.py $D/base_s$s.pt $D/gt2_il8b_s$s.pt $D/gt2_pool_s$s.pt >> docs/results/logs/s25.log 2>&1 || exit 2; fi
  fi
  [ "$DRY" = "1" ] || PRE=1 bash scripts/s25_arm.sh gt2_pool $s configs/s25/base.toml || exit 2
done
[ "$DRY" = "1" ] && exit 0
env "PYTHONPATH=.;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py gt2
