#!/bin/bash
# IL-179 (2026-11-10): the Denver all-hours model cost -0.0009 / -0.0004 by DAY on ERA5, with a truth mismatch (trained on the filled file, scored on the unfilled one). Referee on the
# Denver balloons (IGRA 72469, 2024-25) at 00Z (about 17 h solar) and 12Z (about 05 h solar): installed day model l3_blocal_c4w vs all-hours a24den_c4w, each with its own range map and
# shear map (the balloon scorer has no shuffle / lapse map: same for both). Region via TEMPEST_REGION=configs/region_denver.toml. Waits for the post-P6W test run.
# Log: data/l3.log [IL179]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export TEMPEST_REGION=configs/region_denver.toml
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [IL179] $*" >> data/l3.log; }
until grep -q '\[TESTS\] done after P6W' data/l3.log; do sleep 60; done
log start
for H in 0 12; do
  for spec in "il179_day l3_blocal_c4w" "il179_all a24den_c4w"; do
    set -- $spec; P=models/$1.pt; [ -f $P ] || cp models/$2.pt $P
    $PY -W ignore -u -m tempest.scoring.sonde --model $P --data data/train/denver_full_dpd.npz --profiles data/pilot/profiles_denver_full.zarr --igra data/raw/igra_denver_full --m 199 \
      --first-test-year 2024 --last-test-year 2025 --calib models/$2.calib2021.npz --shear-map models/$2.shearmap2021_cell8.npz --hour $H > data/l3_il179_$1_h$H.log 2>&1 && log "$1 hour $H scored" || log "FAILED $1 hour $H"
  done
  S=$([ $H = 12 ] && echo _12z || echo "")
  { echo "== $(date '+%F %T') IL179 Denver balloons 72469 2024-25 at ${H}Z: day model vs all-hours model"; $PY scripts/compare_headline.py models/il179_day_sonde_cal2021_smap${S}_headline.csv models/il179_all_sonde_cal2021_smap${S}_headline.csv; } >> data/l3_verdicts.txt 2>&1
done
log done
