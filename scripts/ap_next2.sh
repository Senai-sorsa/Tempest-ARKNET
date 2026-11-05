#!/bin/bash
# Autopilot: IL-28 / IL-11 balloon check (seasonal factors for RH + surface scored on balloons). Waits for ap_next.sh. Log data/ap_next2.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
until grep -q "bias_by_year done\|FAILED bias_by_year" data/ap_next.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f
rm -f ${B}_sonde_cal2021_seas_headline.csv
$PY -W ignore -u -m tempest.scoring.sonde --model $B.pt --data data/train/pilot80_dpd.npz --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $B.calib2021.npz --seasonal $B.seasonal2021_rhsfc.npz > data/ap_il28_sonde.log 2>&1 || echo "$(date '+%F %T') FAILED il28 sonde" >> data/ap_next2.log
{ echo "== IL-11 (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_seas_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il28 done" >> data/ap_next2.log
