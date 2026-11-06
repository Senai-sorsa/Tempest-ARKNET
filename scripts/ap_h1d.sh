#!/bin/bash
# Loop 2 H1b: balloon baseline re-run with the same command as the seasonal run (apples to apples), then the comparison. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=. CUDA_VISIBLE_DEVICES=-1
B=models/generator_80_p2f
$PY -W ignore -m tempest.scoring.sonde --model $B.pt --data data/train/pilot80_dpd.npz --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $B.calib2021.npz --extras --shear-map $B.shearmap2021_cell8.npz > data/ap_h1d_sonde.log 2>&1
{ echo "== LOOP2 H1b balloons: seasonal rhprof1km vs same-command baseline"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_smap_headline.csv ${B}_sonde_cal2021_seas_smap_headline.csv | tail -22; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') h1d done" >> data/ap_h1c.log
