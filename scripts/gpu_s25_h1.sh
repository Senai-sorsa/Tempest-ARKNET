#!/bin/bash
# New_Plan 25 H1: prior sample + learned residual (configs/s25/h1_prior.toml) and the N(0,1) control (h1_noise.toml), seeds 0 and 100, paired base. Judge h1.
#   nohup bash scripts/gpu_s25_h1.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_h1.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do for a in h1_prior h1_noise; do bash scripts/s25_arm.sh $a $s configs/s25/$a.toml || exit 2; done; done
JUDGE h1
