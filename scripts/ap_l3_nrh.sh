#!/bin/bash
# L3-36: L3-34 debias lifted Denver -0.19 -> -0.03 but collapsed humidity coverage (RH 12-18 km cov99 0.87 -> 0.47: a mean
# shift on a bounded, skewed variable). Same table with the 45 humidity columns zeroed (models/l3_p2fden.debias2021_nrh.npz),
# alone and in the full stack; plus the full stack with the full table (skipped in L3-35, table did not exist yet).
# Runs after the data-needs queue (scripts/ap_l3_data.sh), back to back.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz B=models/generator_80_p2f
C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz T=models/l3_p2fden.trust2021.npz
DB=models/l3_p2fden.debias2021.npz DN=models/l3_p2fden.debias2021_nrh.npz
log() { echo "$(date '+%F %T') [L3-36] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring' }).Count" | tr -d '\r'; }
# 21:35 the 2 s start raced the data-needs train (its 60 s poll hit the same second), so now it waits for that whole queue
until grep -q "\[DATA all\] data queue done" data/l3.log; do sleep 120; done
while [ "$(busy)" != "0" ]; do sleep 60; done
log start
S="$PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --data $DEN --calib $C"
STK="--trust $T --shuffle --template-cell 8 --shear-map $SM"
$S --model models/l3_p2fden_nrh.pt --debias $DN > data/l3_nrh_den.log 2>&1 && log "den_nrh_debias scored" || log "FAILED den_nrh_debias"
$S --model models/l3_p2fden_nrh.pt --debias $DN $STK > data/l3_nrh_den_stack.log 2>&1 && log "den_nrh_debias_stack scored" || log "FAILED den_nrh_debias_stack"
$S --model models/l3_p2fden_fx.pt --debias $DB $STK > data/l3_fx_den_debias_c8.log 2>&1 && log "den_fx_debias_stack scored" || log "FAILED den_fx_debias_stack"
log done
