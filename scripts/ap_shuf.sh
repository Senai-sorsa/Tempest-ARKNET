#!/bin/bash
# Autopilot IL-83: Schaake shuffle on the climate generator p2f (dependence from real training-year profiles of the same group): diagnostics + ERA5 scoring. Waits for ap_next3. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12 PYTHONPATH=.
until grep -q "il66 done" data/ap_next3.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz
$PY -W ignore -u scripts/diagnose.py $M $C $D --shuffle --out ${B}_shuf_diag > data/ap_il83_diag.log 2>&1
rm -f ${B}_cal2021_shuf_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shuffle > data/ap_il83_score.log 2>&1
{ echo "== IL-83 shuffle (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_shuf_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il83 done" >> data/ap_shuf.log
