#!/bin/bash
# L21 step 1 (2026-11-09): stack the winners on the l21 data. C4w (near-ground vector-wind loss, models/l3_c4w.pt) + a lapse map fitted on ITS stack (calibration, own shear map, shuffle c8),
# scored DAY seeds 0 / 1 / 2 and NIGHT, paired with the confirmed lapse-map stack (models/l3_lapse*, l21 + its lapse map; IL-162). Chained behind gpu_direct_c4w_replicate.sh by its log
# (waits for its SECOND "[C4WREP] done", the first came from the run that failed on a config typo), no queue pattern (B27). Waits for >= 6 GB free RAM before each GPU step.
# Log: data/l3.log [L21S]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
C=models/l3_c4w CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
log() { echo "$(date '+%F %T') [L21S] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
until [ "$(grep -c '\[C4WREP\] done' data/l3.log)" -ge 2 ]; do sleep 60; done
log start
[ -f $LM ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $C.pt --data $A21 --calib $CAL --shear-map $SM --shuffle --template-cell 8 --out $LM > data/l3_l21s_lfit.log 2>&1 && log "lapse map fitted" || { log "FAILED lapse fit"; exit 2; }; }
H() { echo models/$1_cal2021_smap_shufc8_lmap_headline.csv; }
score() {  # score STEM DATA SEED
  local P=models/$1.pt; [ -f $P ] || cp $C.pt $P; [ -f $(H $1) ] && return 0; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model $P --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 --calib $CAL --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/l3_l21s_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
}
verdict() { [ -f $(H $1) ] && [ -f $(H $2) ] && { echo "== $(date '+%F %T') L21S $3"; $PY scripts/compare_headline.py $(H $1) $(H $2)
  echo "physics rows ($1 | $2):"; grep -E "superadiabatic|shear_gt|sfc_jump" models/$1_cal2021_smap_shufc8_lmap_mc.csv | sed 's/^/  a /'; grep -E "superadiabatic|shear_gt|sfc_jump" models/$2_cal2021_smap_shufc8_lmap_mc.csv | sed 's/^/  b /'; } >> data/l3_verdicts.txt 2>&1; }
score l3_c4wl_s0 $DA 0; verdict l3_lapse l3_c4wl_s0 "C4w + lapse map vs l21 + lapse map, DAY seed 0"
score l3_c4wl_s1 $DA 1; verdict l3_lapse_s1 l3_c4wl_s1 "C4w + lapse map vs l21 + lapse map, DAY seed 1"
score l3_c4wl_s2 $DA 2; verdict l3_lapse_s2 l3_c4wl_s2 "C4w + lapse map vs l21 + lapse map, DAY seed 2"
score l3_c4wl_night $NI 0; verdict l3_lapse_night l3_c4wl_night "C4w + lapse map vs l21 + lapse map, NIGHT"
log done
