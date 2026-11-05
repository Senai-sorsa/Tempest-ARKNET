#!/bin/bash
# Autopilot IL-91: shuffle + shear map fitted on the WHOLE shear distribution (not only above the median), on p2f. Waits for the F-7 chain (GPU). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12 PYTHONPATH=.
until grep -q "f7 done" data/ap_f7.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz
$PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $D --calib $C --shuffle --full --out $B.shearmap2021_shuf_full.npz > data/ap_il91_fit.log 2>&1
$PY -W ignore -u scripts/diagnose.py $M $C $D --shuffle --shear-map $B.shearmap2021_shuf_full.npz --out ${B}_stack2_diag > data/ap_il91_diag.log 2>&1
rm -f ${B}_cal2021_smap_shuf_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --shear-map $B.shearmap2021_shuf_full.npz > data/ap_il91_score.log 2>&1
{ echo "== IL-91 shuffle + full-distribution shear map (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_shuf_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il91 done" >> data/ap_stack2.log
