#!/bin/bash
# AU-7 (New_Plan 15.2): the shipped l3_c4w stack (seed 0, the flags of gpu_au1_fair.sh without --fair-baseline) scored with --gauss15
# -> models/l3_c4wl_s0_cal2021_smap_shufc8_lmap_g15_headline.csv (margin_gauss15 beside margin_gauss; 21-day block intervals). Log: data/l3.log [AU7].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
log() { echo "$(date '+%F %T') [AU7] $*" >> data/l3.log; }
log start
$PY -W ignore -u -m tempest.scoring.score --model models/l3_c4wl_s0.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $CAL --shuffle --template-cell 8 \
  --shear-map $SM --lapse-map $LM --gauss15 > data/au7_gauss15_s0.log 2>&1 && log "gauss15 scored" || log "FAILED gauss15"
