#!/bin/bash
# New_Plan 25 H2: analog (k = 8, own year excluded, table <= 200 MB) + learned warp (configs/s25/h2_analog.toml), seeds 0 and 100, paired base;
# also the shuffle-OFF stack (NOSHUF=1, *_noshuf files) the rule reads when present. Judge h2.
#   nohup bash scripts/gpu_s25_h2.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_h2.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do
  bash scripts/s25_arm.sh h2_analog $s configs/s25/h2_analog.toml || exit 2
  NOSHUF=1 bash scripts/s25_arm.sh h2_analog $s configs/s25/h2_analog.toml || exit 2
done
JUDGE h2
