#!/bin/bash
# AU-4 step 0 (New_Plan 15.1): the shipped l3_c4w stack (seed 0, the exact flags of gpu_au1_fair.sh without --fair-baseline) rescored with --daily
# -> models/l3_c4wl_s0_cal2021_smap_shufc8_lmap_daily.csv (per day x band CRPS sums). The headline it rewrites must equal the previous one. Log: data/l3.log [AU4].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
log() { echo "$(date '+%F %T') [AU4] $*" >> data/l3.log; }
log start
$PY -W ignore -u -m tempest.scoring.score --model models/l3_c4wl_s0.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $CAL --shuffle --template-cell 8 \
  --shear-map $SM --lapse-map $LM --daily > data/au4_daily_s0.log 2>&1 && log "daily scored" || log "FAILED daily"
