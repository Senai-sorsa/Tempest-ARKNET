#!/bin/bash
# New_Plan 25 GF1: screen 11 arms (10 ES-beta / variogram / shear-vector-ES arms + the GX2 twES arm) at 3000 steps, seed 0, against
# base3k (seeds 0 and 100 for the noise), full pipeline each; judge gf1_screen (best 2 eligible arms -> s25_gf1_pick.txt); then each pick at
# 6000 steps on seeds 0 and 100 against the paired base (seeds 0 and 100); judge gf1 (also writes s25_gf1_moved.txt for GX1).
# Rules: new_plan_kit/s25_judges.py gf1_screen / gf1 docstrings.
#   nohup bash scripts/gpu_s25_gf1.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdicts: docs/results/logs/kit_s25_gf1*.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
J() { env "PYTHONPATH=.;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py "$@"; }
ARMS="gf1_es0 gf1_es03 gf1_es1 gf1_b05 gf1_b15 gf1_vario002 gf1_vario005 gf1_vario01 gf1_svec005 gf1_svec01 gx2"
for s in 0 100; do STEPS=3000 bash scripts/s25_arm.sh base3k $s configs/s25/base.toml || exit 2; done
for a in $ARMS; do STEPS=3000 bash scripts/s25_arm.sh ${a}_3k 0 configs/s25/$a.toml || exit 2; done
[ "$DRY" = "1" ] && { echo "then: judge gf1_screen; picks x seeds 0,100 at 6000 + base 0,100; judge gf1"; exit 0; }
J gf1_screen | grep -q "VERDICT.*PASS" || exit 0
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
for a in $(cat docs/results/logs/s25_gf1_pick.txt); do
  for s in 0 100; do bash scripts/s25_arm.sh $a $s configs/s25/$a.toml || exit 2; done
done
J gf1
