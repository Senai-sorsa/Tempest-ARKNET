#!/bin/bash
# IL-177 / W-NIGHT (2026-11-10): the vertical-wind (w) head was trained on the 06-21 h day file only (models/whead_clean), so at night it extrapolates (flagged in the tool).
# w targets for the all-hours, day and night l21 files built with `build_wdata --from-cond` (checked against the replayed day w: median |diff| 7e-5 m/s, p99 0.0013, w sd 0.040).
# (1) train a head on the ALL-HOURS rows (same recipe as whead_clean: max-year 2020, early stop 2019-20); (2) for the old and the new head, fit the w range map on generated profiles of the
# INSTALLED generator (l3_c4w + its calibration) on 2021-23 and score 2024-25, separately on the DAY and the NIGHT file (scripts/whead_calib.py; copies per case so no file is overwritten);
# (3) the new head's range map on the all-hours file for the export. Log: data/l3.log [WNIGHT]; tables data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [WNIGHT] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
log start
A=data/train/pilot80_l21_all24_dpd.npz G="--model models/l3_c4w.pt --calib models/l3_c4w.calib2021.npz"
[ -f models/whead_a24.pt ] || { wait_ram; $PY -W ignore -u scripts/whead.py train --data $A --w data/train/pilot80_l21_all24_w.npz --out models/whead_a24.pt --max-year 2020 --val-years 2 > data/wnight_train.log 2>&1 && log "head trained" || { log "FAILED head train"; exit 2; }; }
for part in day night; do
  for spec in "old whead_clean" "new whead_a24"; do
    set -- $spec; H=models/wn_${1}_${part}.pt; [ -f $H ] || cp models/$2.pt $H
    wait_ram
    $PY -W ignore -u scripts/whead_calib.py $G --data data/train/pilot80_l21_${part}_dpd.npz --w data/train/pilot80_l21_${part}_w.npz --head $H --fit-rows 6000 --rows 3000 > data/wnight_${1}_${part}.log 2>&1 && log "$1 head $part scored" || log "FAILED $1 $part"
  done
  { echo "== $(date '+%F %T') W-NIGHT w head, ${part^^} 2024-25 (range map fitted 2021-23 on generated l3_c4w profiles): OLD whead_clean (day-trained) then NEW whead_a24 (all hours); CRPS in cm/s"
    for v in old new; do echo "  $v:"; grep -A9 "version" data/wnight_${v}_${part}.log | sed 's/^/    /'; done; } >> data/l3_verdicts.txt 2>&1
done
H=models/whead_a24.pt
[ -f models/whead_a24.wcalib2021.npz ] || { wait_ram; $PY -W ignore -u scripts/whead_calib.py $G --data $A --w data/train/pilot80_l21_all24_w.npz --head $H --fit-rows 6000 --rows 3000 > data/wnight_new_all24.log 2>&1 && log "new head range map (all hours) for export"; }
log done
