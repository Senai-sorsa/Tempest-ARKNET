#!/bin/bash
# BLOCK 0 F-7b: p2fb = block validation (10 % of 14-day blocks from every year <= 2020), all years <= 2020 train, 2021-23 only calibrate. Runs after the IL-91 rerun. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until [ "$(grep -c 'il91 done' data/ap_stack2.log 2>/dev/null)" -ge 2 ]; do sleep 60; done
VAR=p2fb MAXY=2020 FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f7c_chain.log 2>&1
B=models/generator_80_p2fb; A=models/generator_80_p2f
{ echo "== F-7b p2fb (block validation, calibration years untouched) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-7b p2fb vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
PYTHONPATH=. $PY -W ignore scripts/pitfall_check.py $B.pt $B.calib2021.npz data/train/pilot80_dpd.npz > data/ap_f7c_pitfall.log 2>&1
echo "$(date '+%F %T') f7c done" >> data/ap_f7c.log
