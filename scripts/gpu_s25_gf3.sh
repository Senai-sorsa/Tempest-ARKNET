#!/bin/bash
# New_Plan 25 GF3: rectified flow. F1 = flow matching, same body as base, 8 Euler steps (configs/s25/gf3_f1.toml), seeds 0 and 100;
# F2 = F1 of the same seed + 1000 steps almost-fair CRPS on differentiable 4-step samples (configs/s25/gf3_f2.toml, INIT = F1);
# F3 = F1 with the shuffle OFF (maps refit and scored without it; NOSHUF=1 -> *_noshuf files). Sampler cost of the numpy Euler sampler
# at 4 / 8 / 16 steps -> docs/results/logs/s25_sampler_cost.log. Paired base seeds 0 and 100. Judge gf3 (rule in its docstring).
#   nohup bash scripts/gpu_s25_gf3.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_gf3.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for s in 0 100; do
  bash scripts/s25_arm.sh gf3_f1 $s configs/s25/gf3_f1.toml || exit 2
  INIT=models/s25/gf3_f1_s$s.pt bash scripts/s25_arm.sh gf3_f2 $s configs/s25/gf3_f2.toml || exit 2
  NOSHUF=1 bash scripts/s25_arm.sh gf3_f1 $s configs/s25/gf3_f1.toml || exit 2
done
COST=docs/results/logs/s25_sampler_cost.log
if [ "$DRY" = "1" ]; then echo "sampler cost -> $COST"; exit 0; fi
if [ ! -s $COST ]; then
  . scripts/cap_cpu.sh
  env PYTHONPATH=. $PY -W ignore scripts/s25_sampler_cost.py --model models/s25/gf3_f1_s0.pt --base models/s25/base_s0.pt \
    --data data/train/pilot80_l21_day_dpd.npz > $COST.part 2>&1 && mv $COST.part $COST || { echo "sampler cost FAILED (see $COST.part)"; exit 2; }
fi
env "PYTHONPATH=.;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py gf3
