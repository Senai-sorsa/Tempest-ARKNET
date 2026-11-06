#!/bin/bash
# IL-72 (capped loop 4/6): balloon score of p2f with a median offset fitted on the 2022-23 balloons, vs the plain p2f balloon score. Waits for IL-86. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
until grep -q "il86 done" data/ap_il86.log 2>/dev/null; do sleep 60; done
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --offset-from-year 2022 --offset-to-year 2023 > data/ap_il72_sonde.log 2>&1
{ echo "== IL-72 balloon offset (fit 2022-23) vs p2f (balloons)"; grep "balloon offset fitted" data/ap_il72_sonde.log; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_off_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il72 done" >> data/ap_il72.log
