#!/bin/bash
# New_Plan 25 H3: mixture of 3 soft-gated expert heads (configs/s25/h3_moe.toml), seeds 0 and 100, paired base; gate weights by month on
# 2024-25 -> models/s25/h3_moe_s{0,100}_gate.csv (scripts/s25_gate_month.py, the collapse flag the rule reads). Judge h3.
#   nohup bash scripts/gpu_s25_h3.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_h3.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do
  bash scripts/s25_arm.sh h3_moe $s configs/s25/h3_moe.toml || exit 2
  G=models/s25/h3_moe_s${s}_gate.csv
  [ -e $G ] && continue
  if [ "$DRY" = "1" ]; then echo "gate -> $G"; continue; fi
  . scripts/cap_cpu.sh
  env PYTHONPATH=. .venv/Scripts/python -W ignore scripts/s25_gate_month.py models/s25/h3_moe_s$s.pt data/train/pilot80_l21_day_dpd.npz --out $G.part \
    > docs/results/logs/s25_h3_moe_s${s}_gate.log 2>&1 && mv $G.part $G || { echo "$(date "+%F %T") [S25 h3] FAILED gate csv" >> docs/results/logs/s25.log; exit 2; }
done
JUDGE h3
