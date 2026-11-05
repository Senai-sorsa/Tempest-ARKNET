#!/bin/bash
# Shape half of the verdict: scripts/shape_verdict.sh VAR  -> diagnose generator_80_VAR (calib2021, known drivers, 2024-25), compare with p2f using the p2f seed spread as the tolerance.
# Output: models/generator_80_VAR_shape_diag.csv and a verdict block appended to data/ap_s_verdicts.txt. Needs the seed diags of p2f (ap_il93.sh builds them).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
V=$1; PY=.venv/Scripts/python; D=data/train/pilot80_dpd.npz
M=models/generator_80_$V.pt; C=models/generator_80_$V.calib2021.npz; OUT=models/generator_80_${V}_shape_diag
[ -f $OUT.csv ] || PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $D --out $OUT > data/shape_$V.log 2>&1
NOISE=""; for s in p2f_s1 p2f_s2; do [ -f models/generator_80_${s}_shape_diag.csv ] && NOISE="$NOISE models/generator_80_${s}_shape_diag.csv"; done
{ echo "== SHAPE $V vs p2f (tolerance = p2f seed spread: ${NOISE:-none, 10 percent})"; if [ -n "$NOISE" ]; then $PY scripts/compare_shape.py models/generator_80_p2f_shape_diag.csv $OUT.csv --noise $NOISE; else $PY scripts/compare_shape.py models/generator_80_p2f_shape_diag.csv $OUT.csv; fi; } >> data/ap_s_verdicts.txt 2>&1
