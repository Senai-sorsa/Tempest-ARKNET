#!/bin/bash
# Autopilot IL-89: shear map with seven layer groups (fit on 6000 rows of 2021-23): ERA5 + balloon scoring, physics table, shear-by-layer table. Waits for ap_stack. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12 PYTHONPATH=.
until grep -q "il88 done" data/ap_stack.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
$PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $D --calib $C --groups 7 --rows 6000 --out $B.shearmap2021_g7.npz > data/ap_il89_fit.log 2>&1
rm -f ${B}_cal2021_smap_headline.csv ${B}_sonde_cal2021_smap_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shear-map $B.shearmap2021_g7.npz > data/ap_il89_score.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shear-map $B.shearmap2021_g7.npz > data/ap_il89_sonde.log 2>&1
{ echo "== IL-89 seven-group shear map (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_headline.csv | tail -5
  echo "== IL-89 (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_smap_headline.csv | tail -5
  echo "== IL-89 shear by layer with the seven-group map"; $PY -W ignore scripts/shear_by_layer.py $M $C $D --shear-map $B.shearmap2021_g7.npz | head -9; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il89 done" >> data/ap_il89.log
