#!/bin/bash
# New_Plan 25 GX2: threshold-weighted ES on u, v over 0-18 km at q90 (configs/s25/gx2.toml, twes_weight 0.1), 6000 steps, seeds 0 and 100,
# against the paired base (seeds 0 and 100), full pipeline (the shear map refit comes before the p99 read). Judge gx2 (rule in its docstring).
# A GX2 run made earlier as a GF1 pick is reused (same names), never retrained.
#   nohup bash scripts/gpu_s25_gx2.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_gx2.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do bash scripts/s25_arm.sh gx2 $s configs/s25/gx2.toml || exit 2; done
[ "$DRY" = "1" ] && exit 0
env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py gx2
