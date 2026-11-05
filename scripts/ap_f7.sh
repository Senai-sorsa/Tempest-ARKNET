#!/bin/bash
# BLOCK 0 F-7: p2f retrained with separate early-stopping (2019-20) and calibration (2021-23) windows; train <= 2018. Waits for the GPU (phase2_variant.sh checks). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il88 done" data/ap_stack.log 2>/dev/null; do sleep 60; done
# the balloon scorer now shifts the whole low-level temperature to the site elevation (F-22): rescore the p2f baseline with the same code first
$PY -W ignore -u -m tempest.scoring.sonde --model models/generator_80_p2f.pt --data data/train/pilot80_dpd.npz --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/generator_80_p2f.calib2021.npz --extras > data/ap_f22_p2f_sonde.log 2>&1
echo "$(date '+%F %T') p2f balloons rescored with the F-22 site shift" >> data/ap_f7.log
VAR=p2fv MAXY=2020 FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f7_chain.log 2>&1
B=models/generator_80_p2fv; A=models/generator_80_p2f
{ echo "== F-7 p2fv (split windows) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-7 p2fv vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
PYTHONPATH=. $PY -W ignore scripts/pitfall_check.py $B.pt $B.calib2021.npz data/train/pilot80_dpd.npz > data/ap_f7_pitfall.log 2>&1
echo "$(date '+%F %T') f7 done" >> data/ap_f7.log
