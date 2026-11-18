#!/bin/bash
# New_Plan 25 GT1: height-autoregressive generator, 7 blocks bottom-up (configs/s25/gt1.toml), seeds 0 and 100, paired base;
# error per block comes from the s25 shape step (--blocks 7, every arm). Judge gt1.
#   nohup bash scripts/gpu_s25_gt1.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_gt1.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do bash scripts/s25_arm.sh gt1 $s configs/s25/gt1.toml || exit 2; done
JUDGE gt1
