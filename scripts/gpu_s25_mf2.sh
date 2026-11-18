#!/bin/bash
# New_Plan 25 MF2: Reverse Markov Learning, K = 3 and K = 5 (configs/s25/mf2_k3.toml, mf2_k5.toml), seeds 0 and 100, paired base. Judge mf2.
#   nohup bash scripts/gpu_s25_mf2.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_mf2.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do for a in mf2_k3 mf2_k5; do bash scripts/s25_arm.sh $a $s configs/s25/$a.toml || exit 2; done; done
JUDGE mf2
