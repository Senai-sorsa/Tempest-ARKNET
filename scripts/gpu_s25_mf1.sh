#!/bin/bash
# New_Plan 25 MF1: one-step mlp student distilled from the GF3 teacher of the same seed (energy distance, distill_m 8).
# Gate: the teacher arm is the first line of docs/results/logs/s25_gf3_pick.txt (written by the gf3 judge); empty -> log and exit.
#   nohup bash scripts/gpu_s25_mf1.sh > /dev/null 2>&1 &         log: docs/results/logs/s25.log, verdict: docs/results/logs/kit_s25_mf1.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { [ "$DRY" = "1" ] && exit 0; env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
T=$(head -1 docs/results/logs/s25_gf3_pick.txt 2>/dev/null | tr -d "\r ")
if [ -z "$T" ]; then [ "$DRY" = "1" ] && echo "DRY: gate closed, would exit" || echo "$(date "+%F %T") [S25 mf1] gate closed: no GF3 pick (run GF3 first)" >> docs/results/logs/s25.log; [ "$DRY" = "1" ] && T=gf3_f1 || exit 0; fi
for s in 0 100; do
  [ -f models/s25/${T}_s$s.pt ] || [ "$DRY" = "1" ] || { echo "$(date "+%F %T") [S25 mf1] FAILED missing teacher models/s25/${T}_s$s.pt" >> docs/results/logs/s25.log; exit 2; }
  bash scripts/s25_arm.sh mf1 $s configs/s25/mf1.toml "distill_teacher=\"models/s25/${T}_s$s.pt\"" || exit 2
done
JUDGE mf1
