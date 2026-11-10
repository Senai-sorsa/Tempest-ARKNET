#!/bin/bash
# IL-184 (2026-11-10): Denver vertical-wind head. Denver ships no w head; w targets from the Earthmover omega (data/raw/era5_em_denver_full/w.zarr, build_wdata --from-cond).
# Head trained on the Denver ALL-HOURS rows (recipe of whead_a24: max-year 2020, early stop 2019-20). Range maps (whead_calib.py, fit 2021-23, score 2024-25) for each Denver generator:
# the day set (l3_blocal_c4w, scored on the day file) and the all-hours set (a24den_c4w, scored on the all-hours file and on the night file). Copies per case so no file is overwritten.
# Log: data/l3.log [WDEN]; tables data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [WDEN] $*" >> data/l3.log; }
log start
A=data/train/denver_full_fill_all24_dpd.npz AW=data/train/denver_full_fill_all24_w.npz
[ -f models/whead_den.pt ] || { $PY -W ignore -u scripts/whead.py train --data $A --w $AW --out models/whead_den.pt --max-year 2020 --val-years 2 > data/wden_train.log 2>&1 && log "head trained" || { log "FAILED head train"; exit 2; }; }
run() {  # run TAG GENERATOR DATA W
  local H=models/whead_den_$1.pt; [ -f $H ] || cp models/whead_den.pt $H
  $PY -W ignore -u scripts/whead_calib.py --model models/$2.pt --calib models/$2.calib2021.npz --data $3 --w $4 --head $H --fit-rows 6000 --rows 3000 > data/wden_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
  { echo "== $(date '+%F %T') Denver w head ($1: generator $2, $(basename $3)); CRPS cm/s"; grep -A9 "version" data/wden_$1.log | sed 's/^/  /'; } >> data/l3_verdicts.txt 2>&1
}
run dayset l3_blocal_c4w data/train/denver_full_dpd.npz data/train/denver_full_w.npz
run allset a24den_c4w $A $AW
run allnight a24den_c4w data/train/denver_full_fill_night_dpd.npz data/train/denver_full_fill_night_w.npz
log done
