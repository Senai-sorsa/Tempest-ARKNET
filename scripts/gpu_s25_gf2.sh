#!/bin/bash
# New_Plan 25 GF2: lr {3e-4, 1e-3, 3e-3} x wd {1e-5, 1e-4, 1e-3} at 3000 steps, seed 0, train only (+ the shipped centre cell on seed 100
# for the noise), judge (new_plan_kit/s25_judges.py gf2, rule in its docstring); if PASS, the follow-up: best cell, batch 16384, lr x 2,
# 12000 steps (gf2_big), reported by the gf2_follow judge.
#   nohup bash scripts/gpu_s25_gf2.sh > /dev/null 2>&1 &        log: docs/results/logs/s25.log, verdicts: docs/results/logs/kit_s25_gf2*.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python J="env PYTHONPATH=.;new_plan_kit;scripts $PY -W ignore new_plan_kit/s25_judges.py"
for lr in 3e-4 1e-3 3e-3; do for wd in 1e-5 1e-4 1e-3; do
  STEPS=3000 STAGE=train bash scripts/s25_arm.sh gf2_l${lr}_w${wd} 0 configs/s25/base.toml lr=$lr weight_decay=$wd || exit 2
done; done
STEPS=3000 STAGE=train bash scripts/s25_arm.sh gf2_l1e-3_w1e-4 100 configs/s25/base.toml lr=1e-3 weight_decay=1e-4 || exit 2
[ "$DRY" = "1" ] && exit 0
$J gf2 | grep -q "VERDICT.*PASS" || exit 0
best=$(head -1 docs/results/logs/s25_gf2_pick.txt)                 # gf2_l<lr>_w<wd>
lr=${best#gf2_l}; lr=${lr%%_w*}; wd=${best##*_w}
lr2=$($PY -c "print(2 * float('$lr'))")
STEPS=12000 STAGE=train bash scripts/s25_arm.sh gf2_big 0 configs/s25/base.toml lr=$lr2 weight_decay=$wd batch=16384 || exit 2
$J gf2_follow
