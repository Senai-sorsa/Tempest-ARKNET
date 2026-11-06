#!/bin/bash
# IL-86 (capped loop 1/6): fit the generator PIT recalibration on 2021-23 (unknown drivers), score on ERA5 2024-25 and the shape diagnostics, vs p2f. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f
export PYTHONPATH=.
$PY -W ignore -u scripts/il86_fit.py $M $C $D > data/ap_il86_fit.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --pit-recal $B.pitrecal2021.npz > data/ap_il86_score.log 2>&1
$PY -W ignore scripts/diagnose.py $M $C $D --pit-recal $B.pitrecal2021.npz --out ${B}_pit_diag > data/ap_il86_diag.log 2>&1
{ echo "== IL-86 PIT recalibration vs p2f (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_pit_headline.csv | tail -5
  echo "== IL-86 shape vs p2f"; $PY scripts/compare_shape.py ${B}_shape_diag.csv ${B}_pit_diag.csv --noise models/generator_80_p2f_s1_shape_diag.csv models/generator_80_p2f_s2_shape_diag.csv; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il86 done" >> data/ap_il86.log
