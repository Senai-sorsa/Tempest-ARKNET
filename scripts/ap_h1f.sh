#!/bin/bash
# Loop 2 H1/H1b: variants of the final stack A with a damped PIT map and/or seasonal widths for the RH profile only; shape vs stack A (seed-spread tolerance) and ERA5 headline. CPU only. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=. CUDA_VISIBLE_DEVICES=-1
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f
SM=$B.shearmap2021_cell8.npz; PIT=$B.pitrecal2021.npz; SE=$B.seasonal2021_rhprof.npz
NOISE="models/generator_80_p2f_s1_shape_diag.csv models/generator_80_p2f_s2_shape_diag.csv"
STACK="--shuffle --template-cell 8 --shear-map $SM"
for V in "c7:--pit-recal $PIT --pit-damp 0.5 --seasonal $B.seasonal2021_prof1km.npz" "c8:--pit-recal $PIT --pit-damp 0.5 --seasonal $B.seasonal2021_TRh1km.npz"; do
  N=${V%%:*}; F=${V#*:}
  $PY -W ignore scripts/diagnose.py $M $C $D $STACK $F --out ${B}_L2$N > data/ap_h1f_$N.log 2>&1
  { echo "== LOOP2 $N ($F) vs stack A: shape"; $PY scripts/compare_shape.py ${B}_cell8_refit_diag.csv ${B}_L2$N.csv --noise $NOISE; } >> data/ap_s_verdicts.txt 2>&1
done
echo "$(date '+%F %T') h1f done" >> data/ap_h1.log
