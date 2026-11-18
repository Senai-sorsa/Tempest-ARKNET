#!/bin/bash
# New_Plan 25 H4: EOF basis (95 % variance) with AR(1) coefficients (configs/s25/h4_eof.toml), seeds 0 and 100, paired base. Judge h4.
#   nohup bash scripts/gpu_s25_h4.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_h4.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do bash scripts/s25_arm.sh h4_eof $s configs/s25/h4_eof.toml || exit 2; done
JUDGE h4
