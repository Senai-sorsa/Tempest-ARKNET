#!/bin/bash
# Autopilot IL-88: shuffle + shear map stack on p2f (map fitted on shuffled samples) vs p2f: diagnostics and ERA5 scoring. Waits for ap_next4. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12 PYTHONPATH=.
until grep -q "il60 done" data/ap_next4.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz
$PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $D --calib $C --shuffle --out $B.shearmap2021_shuf.npz > data/ap_il88_fit.log 2>&1
$PY -W ignore -u scripts/diagnose.py $M $C $D --shuffle --shear-map $B.shearmap2021_shuf.npz --out ${B}_stack_diag > data/ap_il88_diag.log 2>&1
rm -f ${B}_cal2021_shuf_smap_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle --shear-map $B.shearmap2021_shuf.npz > data/ap_il88_score.log 2>&1
{ echo "== IL-88 stack: shuffle + shear map (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_smap_shuf_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il88 done" >> data/ap_stack.log
