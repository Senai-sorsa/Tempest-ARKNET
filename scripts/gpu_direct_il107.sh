#!/bin/bash
# IL-107 (2026-11-10): tail-weighted baseline for the installed NM/TX stack (l3_c4w + calibration + shuffle c8 + shear map + lapse map), DAY 21-level truth and NIGHT, seed 0, `score --tail`
# (threshold-weighted CRPS above the climatological 99th percentile + exceedance rates of the wind speed at 10 / 100 / 300 m / 1 / 3 km and the 10 m - 1 km shear). Waits for the G3 test run.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [IL107] $*" >> data/l3.log; }
until grep -q 'TESTS\] done after G3' data/l3.log; do sleep 30; done
C=models/l3_c4w
for spec in "il107_day data/train/pilot80_l21_day_dpd.npz" "il107_night data/train/pilot80_l21_night_dpd.npz"; do
  set -- $spec; P=models/$1.pt; [ -f $P ] || cp $C.pt $P
  $PY -W ignore -u -m tempest.scoring.score --model $P --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --tail --seed 0 --calib $C.calib2021.npz --shuffle --template-cell 8 \
    --shear-map $C.shearmap2021_cell8.npz --lapse-map $C.lapsemap2021.npz > data/l3_il107_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
done
log done
