#!/bin/bash
# E2: rescore the final system (stack A) on 2024-25 and compare with the logged IL-16 numbers (same seeds: must match within noise). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f; SM=$B.shearmap2021_cell8.npz; P=data/pilot/profiles80.zarr
mkdir -p data/e2; cp ${B}_cal2021_smap_shufc8_headline.csv data/e2/era5_before.csv; cp ${B}_sonde_cal2021_smap_headline.csv data/e2/sonde_before.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --template-cell 8 --shear-map $SM > data/e2/score.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --shear-map $SM > data/e2/sonde.log 2>&1
$PY - <<'PYEOF' > data/e2/compare.txt 2>&1
import pandas as pd
for n, new in (("era5", "models/generator_80_p2f_cal2021_smap_shufc8_headline.csv"), ("sonde", "models/generator_80_p2f_sonde_cal2021_smap_headline.csv")):
    a, b = pd.read_csv(f"data/e2/{n}_before.csv"), pd.read_csv(new)
    c = [x for x in a.columns if x.startswith(("skill15_unknown", "cov99_unknown"))]
    d = (b[c] - a[c]).abs().max()
    print(n, "max |difference| over the", len(a), "cells:", d.round(6).to_dict())
PYEOF
echo "$(date '+%F %T') e2 done" >> data/e2/done.log
