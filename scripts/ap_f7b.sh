#!/bin/bash
# BLOCK 0 F-7 (relaunch): p2fv = p2f with separate early-stopping (2019-20) and calibration (2021-23) windows. The first launch collided with the p2f balloon rescoring (GPU out of memory). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
VAR=p2fv MAXY=2020 FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f7_chain.log 2>&1
B=models/generator_80_p2fv; A=models/generator_80_p2f
{ echo "== F-7 p2fv (split windows) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-7 p2fv vs p2f (balloons, both with the F-22 site shift)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
PYTHONPATH=. $PY -W ignore scripts/pitfall_check.py $B.pt $B.calib2021.npz data/train/pilot80_dpd.npz > data/ap_f7_pitfall.log 2>&1
echo "$(date '+%F %T') f7 done" >> data/ap_f7.log
