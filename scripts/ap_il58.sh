#!/bin/bash
# Autopilot IL-58: shear-space quantile map on p2f (fit on 2021-23, ERA5 targets), scored on ERA5 and balloons 2024-25, plus the physics shear table.
# Waits for the shear training group. Log data/ap_il58.log, verdict in data/ap_shear_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
until grep -q "shear training group done" data/ap_shear.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
[ -f $B.shearmap2021.npz ] || $PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $D --calib $C > data/ap_il58_fit.log 2>&1 || echo "$(date '+%F %T') FAILED il58 fit" >> data/ap_il58.log
rm -f ${B}_cal2021_smap_headline.csv ${B}_sonde_cal2021_smap_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shear-map $B.shearmap2021.npz > data/ap_il58_score.log 2>&1 || echo "$(date '+%F %T') FAILED il58 score" >> data/ap_il58.log
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shear-map $B.shearmap2021.npz > data/ap_il58_sonde.log 2>&1 || echo "$(date '+%F %T') FAILED il58 sonde" >> data/ap_il58.log
PYTHONPATH=. $PY -W ignore - >> data/ap_shear_verdicts.txt 2>&1 <<'PYEOF'
import numpy as np
from scripts import physics
from tempest.calibrate import shear_map
t = dict(np.load("models/generator_80_p2f.shearmap2021.npz"))
r = physics.table("models/generator_80_p2f.pt", "models/generator_80_p2f.calib2021.npz", "data/train/pilot80_dpd.npz", rows=4000, apply_extra=lambda x: shear_map.apply(t, x))
print("== IL-58 physics (shear p50/p99/p99.9; truth, calibrated, calibrated+shear map)")
print(r[r.set != "raw"][["band", "set", "shear_p50", "shear_p99", "shear_p999"]].round(2).to_string(index=False))
PYEOF
{ echo "== IL-58 (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_headline.csv | tail -5
  echo "== IL-58 (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_smap_headline.csv | tail -5; } >> data/ap_shear_verdicts.txt 2>&1
echo "$(date '+%F %T') il58 done" >> data/ap_il58.log
