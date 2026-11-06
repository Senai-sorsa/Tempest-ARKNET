#!/bin/bash
# IL-16 (capped loop 6/6): the stack check. A = shuffle (2 degree templates) + refit shear map; B = A + seasonal widths for RH and surface. ERA5 (score + shape) and balloons (sonde: shear map and seasonal; the balloon scorer has no shuffle). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f; SM=$B.shearmap2021_cell8.npz; SE=$B.seasonal2021_rhsfc.npz; P=data/pilot/profiles80.zarr
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --template-cell 8 --shear-map $SM > data/ap_il16_scoreA.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --template-cell 8 --shear-map $SM --seasonal $SE > data/ap_il16_scoreB.log 2>&1
$PY -W ignore scripts/diagnose.py $M $C $D --shuffle --template-cell 8 --shear-map $SM --seasonal $SE --out ${B}_stackB_diag > data/ap_il16_diagB.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --shear-map $SM > data/ap_il16_sondeA.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --shear-map $SM --seasonal $SE > data/ap_il16_sondeB.log 2>&1
NOISE="models/generator_80_p2f_s1_shape_diag.csv models/generator_80_p2f_s2_shape_diag.csv"
{ echo "== IL-16 stack A (shuffle c8 + shear map) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_shufc8_headline.csv | tail -5
  echo "== IL-16 stack B (A + seasonal rhsfc) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_seas_smap_shufc8_headline.csv | tail -5
  echo "== IL-16 stack A vs p2f (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_smap_headline.csv | tail -5
  echo "== IL-16 stack B vs p2f (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_seas_smap_headline.csv | tail -5
  echo "== IL-16 shape: stack A vs p2f"; $PY scripts/compare_shape.py ${B}_shape_diag.csv ${B}_cell8_refit_diag.csv --noise $NOISE
  echo "== IL-16 shape: stack B vs p2f"; $PY scripts/compare_shape.py ${B}_shape_diag.csv ${B}_stackB_diag.csv --noise $NOISE; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il16 done" >> data/ap_il16.log
