#!/bin/bash
# New_Plan 25 GX1: depth-2 signature loss (sig_weight 0.05) on all heights and on every 2nd height, seeds 0 and 100, paired base.
# Gate: runs only if docs/results/logs/s25_gf1_moved_pick.txt says YES (written by the gf1 judge); otherwise logs and exits before training.
#   nohup bash scripts/gpu_s25_gx1.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_gx1.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
P=docs/results/logs/s25_gf1_moved_pick.txt
if [ "$(cat $P 2>/dev/null | tr -d "\r\n ")" != "YES" ]; then [ "$DRY" = "1" ] && echo "DRY: gate closed, would exit" || echo "$(date "+%F %T") [S25 gx1] gate closed: $P is not YES (run GF1 first)" >> docs/results/logs/s25.log; [ "$DRY" = "1" ] || exit 0; fi
for s in 0 100; do for a in gx1 gx1_s2; do bash scripts/s25_arm.sh $a $s configs/s25/$a.toml || exit 2; done; done
JUDGE gx1
