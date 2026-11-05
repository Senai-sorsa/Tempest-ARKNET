#!/bin/bash
# IL-94: the tool's version of the shape stack (shuffle with templates pooled over grid points + the whole-distribution shear map) scored on ERA5 + shape diagnostics, vs p2f and vs the per-point-template stack (IL-91). Waits for IL-93. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il93 done" data/ap_il93.log 2>/dev/null; do sleep 60; done
sleep 60
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f; SM=$B.shearmap2021_shuf_full.npz
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --pooled-template --shear-map $SM > data/ap_il94_score.log 2>&1
PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $D --shuffle --pooled-template --shear-map $SM --out ${B}_pooled_stack_diag > data/ap_il94_diag.log 2>&1
PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $D --shuffle --shear-map $SM --out ${B}_perpoint_stack_diag > data/ap_il94_diag2.log 2>&1
{ echo "== IL-94 tool stack (pooled templates + full shear map) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_shufpool_headline.csv | tail -5
  echo "== IL-94 shape vs p2f (seed spread as tolerance)"; NOISE=""; for s in p2f_s1 p2f_s2; do [ -f models/generator_80_${s}_shape_diag.csv ] && NOISE="$NOISE models/generator_80_${s}_shape_diag.csv"; done
  $PY scripts/compare_shape.py models/generator_80_p2f_shape_diag.csv ${B}_pooled_stack_diag.csv --noise $NOISE
  echo "== IL-94 shape: pooled templates vs per-point templates (IL-91 stack)"; $PY scripts/compare_shape.py ${B}_perpoint_stack_diag.csv ${B}_pooled_stack_diag.csv; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il94 done" >> data/ap_il94.log
