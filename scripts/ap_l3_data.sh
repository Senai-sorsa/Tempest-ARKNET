#!/bin/bash
# Data-needs runs (docs/DATA_NEEDS.md): how much data the generator needs, measured, not assumed.
# p2f config, trained on a thinned copy of the data (fewer years / points / hours), calibrated and scored on the FULL
# data 2024-25 (so unseen points and hours count), compared with the full-data model. Starts after the loop-3 queue
# (data/l3.log "queue done") so only one GPU job runs at a time. Every step skips when its output exists.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz; DEN=data/train/denver_full_dpd.npz; VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [DATA $1] $2" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|calibrate.joint|scoring' }).Count" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ]; do sleep 60; done; }

one() {  # one NAME DATA BASELINE_HEADLINE TRAIN_ARGS...
  local V=$1 D=$2 B=$3; shift 3
  local M=models/l3_d_$V.pt C=models/l3_d_$V.calib2021.npz H=models/l3_d_${V}_cal2021_headline.csv
  [ -f $H ] && return 0
  [ -f $B ] || { log $V "no baseline $B yet"; return; }
  log $V "start ($*)"
  if [ ! -f $M ]; then
    wait_gpu
    $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --config configs/generator_p2f.toml "$@" > data/l3_train_d_$V.log 2>&1 && mv $M.part $M || { log $V "FAILED train"; return; }
  fi
  if [ ! -f $C ]; then
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_d_$V.log 2>&1 || { log $V "FAILED spread"; return; }
  fi
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/l3_score_d_$V.log 2>&1 || { log $V "FAILED score"; return; }
  log $V scored
  { echo "== $(date '+%F %T') DATA $V ($*) vs full data"; $PY scripts/compare_headline.py $B $H; } >> $VLOG 2>&1
}

until grep -q "\[L3 all\] queue done" data/l3.log; do sleep 300; done
P2F=models/generator_80_p2f_cal2021_headline.csv; BL=models/l3_blocal_cal2021_headline.csv
# NM/TX: years, points, hours (D1-D6)
one yrs2011  $NT $P2F --min-year 2011
one pts2     $NT $P2F --min-year 1991 --point-stride 2
one hcyc16   $NT $P2F --min-year 1991 --hour-cycle 16
one hcyc4    $NT $P2F --min-year 1991 --hour-cycle 4
one pts2hcyc16 $NT $P2F --min-year 1991 --point-stride 2 --hour-cycle 16
one yrs2001  $NT $P2F --min-year 2001
# a new region (Denver, vs B-local): how much of it a box needs (D7)
one den_yrs2011  $DEN $BL --min-year 2011
one den_hcyc16   $DEN $BL --min-year 1991 --hour-cycle 16
log all "data queue done"
