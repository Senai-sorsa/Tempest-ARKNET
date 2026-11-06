#!/bin/bash
# IL-96: refit the full shear map behind 2 degree block shuffle templates, then check shape. CPU only (the GPU belongs to the retrain chain). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f
export CUDA_VISIBLE_DEVICES=-1 PYTHONPATH=.
$PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $D --calib $C --shuffle --full --template-cell 8 --device cpu --out $B.shearmap2021_cell8.npz > data/ap_il96_fit.log 2>&1
$PY -W ignore scripts/diagnose.py $M $C $D --shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz --out ${B}_cell8_refit_diag > data/ap_il96_diag.log 2>&1
{ echo "== IL-96 shear map refit behind 2 degree templates vs p2f"; NOISE=""; for s in p2f_s1 p2f_s2; do NOISE="$NOISE models/generator_80_${s}_shape_diag.csv"; done
  $PY scripts/compare_shape.py models/generator_80_p2f_shape_diag.csv ${B}_cell8_refit_diag.csv --noise $NOISE
  echo "== IL-96 refit vs the old map behind 2 degree templates"; $PY scripts/compare_shape.py ${B}_cell8_stack_diag.csv ${B}_cell8_refit_diag.csv; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il96 done" >> data/ap_il96.log
