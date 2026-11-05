#!/bin/bash
# Autopilot: IL-66 long-window median shift (2011-2023, no 2024-25 data), then the fixed shape diagnostics rerun (IL-44b). Waits for the shear chain and IL-58.
# Log data/ap_next3.log, verdict in data/ap_s_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
until grep -q "il58 done\|FAILED il58" data/ap_il58.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
[ -f $B.shift2011.npz ] || $PY -W ignore -u -m tempest.calibrate.shift --model $M --data $D --calib $C --from-year 2011 --year 2023 --rows 24000 > data/ap_il66_fit.log 2>&1 || echo "$(date '+%F %T') FAILED il66 fit" >> data/ap_next3.log
rm -f ${B}_cal2021_shift_headline.csv ${B}_sonde_cal2021_shift_headline.csv
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shift $B.shift2011.npz > data/ap_il66_score.log 2>&1 || echo "$(date '+%F %T') FAILED il66 score" >> data/ap_next3.log
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shift $B.shift2011.npz > data/ap_il66_sonde.log 2>&1 || echo "$(date '+%F %T') FAILED il66 sonde" >> data/ap_next3.log
{ echo "== IL-66 long-window shift (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021_shift_headline.csv | tail -5
  echo "== IL-66 (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_shift_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
PYTHONPATH=. $PY -W ignore -u scripts/diagnose.py $M $C $D --out ${B}_base2 > data/ap_il44b.log 2>&1
PYTHONPATH=. $PY -W ignore -u scripts/diagnose.py $M $C $D --shift $B.shift2011.npz --out ${B}_shift2011_diag > data/ap_il66_diag.log 2>&1
echo "$(date '+%F %T') il66 done" >> data/ap_next3.log
