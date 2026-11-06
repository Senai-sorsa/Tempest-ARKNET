#!/bin/bash
# Loop 3 runner (Code-Modifications/LOOP3.md): scripts/ap_l3.sh [VARIANT ...]  (default: the queue below).
# Per variant: train configs/generator_l3_V.toml on NM/TX -> range calibration 2021-23 -> score 2024-25 -> verdict vs p2f
# (tolerance = p2f seeds s1/s2) -> shape verdict -> zero-shot Denver score with the NM/TX calibration (once the Denver
# dataset exists). Every step skips when its output exists, so a relaunch resumes. One GPU job at a time.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT0=data/train/pilot80_dpd.npz; DEN0=data/train/denver_full_dpd.npz
# a config with the line "# l3-data: l3x" uses the overlay with terrain / clock / climatology columns (scripts/l3_overlay.py)
VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [L3 $1] $2" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|calibrate.joint|scoring' }).Count" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ]; do sleep 60; done; }

score() {  # score MODEL CALIB DATA LOGNAME
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $1 --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --calib $2 --extras > data/l3_score_$4.log 2>&1
}

braw() {  # B-raw: the adopted p2f zero-shot at Denver (the Denver baseline)
  [ -f models/l3_braw.pt ] || cp models/generator_80_p2f.pt models/l3_braw.pt
  [ -f models/l3_braw_cal2021_headline.csv ] || { score models/l3_braw.pt models/generator_80_p2f.calib2021.npz $DEN0 braw && log braw "denver scored"; }
}

denver() {  # denver V MODEL CALIB: zero-shot Denver score of an NM/TX model (copied so output names do not clash)
  [ -f $DEN0 ] || return 0
  braw
  local DEN=$DEN0
  if [ "$4" = l3x ]; then
    DEN=${DEN0%.npz}_l3x.npz
    [ -f $DEN ] || PYTHONPATH=. $PY -W ignore scripts/l3_overlay.py $DEN0 $DEN >> data/l3_overlay_denver.log 2>&1 || { log $1 "FAILED denver overlay"; return; }
  fi
  local DM=models/l3_${1}_den.pt
  [ -f ${DM%.pt}_cal2021_headline.csv ] && return 0
  cp $2 $DM
  score $DM $3 $DEN ${1}_den && log $1 "denver scored" || log $1 "FAILED denver score"
  { echo "== $(date '+%F %T') DENVER $1 vs B-raw (p2f zero-shot)"; $PY scripts/compare_headline.py models/l3_braw_cal2021_headline.csv ${DM%.pt}_cal2021_headline.csv; } >> $VLOG 2>&1
}

blocal() {  # L3-0c/0d: p2f config trained, calibrated and scored on Denver itself (upper bound) + seed 100 (Denver tolerance)
  [ -f $DEN0 ] || return 0
  braw; local V
  for V in blocal blocal_s1; do
    local M=models/l3_$V.pt C=models/l3_$V.calib2021.npz H=models/l3_${V}_cal2021_headline.csv
    [ -f $H ] && continue
    log $V start
    if [ ! -f $M ]; then
      wait_gpu
      $PY -u -m tempest.generator.train --data $DEN0 --out $M.part --max-year 2023 --min-year 1991 --config configs/generator_l3_$V.toml > data/l3_train_$V.log 2>&1 && mv $M.part $M || { log $V "FAILED train"; return; }
    fi
    if [ ! -f $C ]; then
      wait_gpu
      $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $DEN0 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$V.log 2>&1 || { log $V "FAILED spread"; return; }
    fi
    score $M $C $DEN0 $V || { log $V "FAILED score"; return; }
    log $V "denver scored"
  done
  { echo "== $(date '+%F %T') DENVER B-local vs B-raw"; $PY scripts/compare_headline.py models/l3_braw_cal2021_headline.csv models/l3_blocal_cal2021_headline.csv
    echo "== DENVER seed tolerance blocal_s1 vs blocal"; $PY scripts/compare_headline.py models/l3_blocal_cal2021_headline.csv models/l3_blocal_s1_cal2021_headline.csv; } >> $VLOG 2>&1
}

run() {  # run V: one NM/TX variant
  local V=$1 M=models/l3_$1.pt C=models/l3_$1.calib2021.npz CFG=configs/generator_l3_$1.toml
  [ -f $CFG ] || { log $V "no config $CFG"; return; }
  local X=; grep -q '^# l3-data: l3x' $CFG && X=l3x
  local NT=$NT0; [ -n "$X" ] && NT=${NT0%.npz}_l3x.npz
  [ -f $NT ] || PYTHONPATH=. $PY -W ignore scripts/l3_overlay.py $NT0 $NT >> data/l3_overlay_nmtx.log 2>&1
  log $V start
  if [ ! -f $M ]; then
    wait_gpu
    $PY -u -m tempest.generator.train --data $NT --out $M.part --max-year 2023 --min-year 1991 --config $CFG > data/l3_train_$V.log 2>&1 && mv $M.part $M || { log $V "FAILED train"; return; }
  fi
  log $V trained
  if [ ! -f $C ]; then
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $NT --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$V.log 2>&1 || { log $V "FAILED spread"; return; }
  fi
  local H=models/l3_${V}_cal2021_headline.csv
  if [ ! -f $H ]; then score $M $C $NT $V || { log $V "FAILED score"; return; }; fi
  log $V "nm/tx scored"
  { echo "== $(date '+%F %T') NMTX $V vs p2f"; $PY scripts/compare_headline.py models/generator_80_p2f_cal2021_headline.csv $H; } >> $VLOG 2>&1
  local SD=models/l3_${V}_shape_diag
  [ -f $SD.csv ] || { wait_gpu; PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $NT --out $SD > data/l3_shape_$V.log 2>&1; }
  { echo "== SHAPE $V vs p2f"; $PY scripts/compare_shape.py models/generator_80_p2f_shape_diag.csv $SD.csv --noise models/generator_80_p2f_s1_shape_diag.csv models/generator_80_p2f_s2_shape_diag.csv; } >> $VLOG 2>&1
  denver $V $M $C $X
  log $V done
}

if [ ! -f $VLOG ]; then  # once: the NM/TX seed tolerance (p2f s1/s2 vs p2f)
  for s in s1 s2; do { echo "== NMTX seed tolerance p2f_$s vs p2f"; $PY scripts/compare_headline.py models/generator_80_p2f_cal2021_headline.csv models/generator_80_p2f_${s}_cal2021_headline.csv; } >> $VLOG 2>&1; done
fi

Q=${*:-nolatlon sh10 sh20 siren sh10ctx w768 terrain clocks clim ctxall thead}
for V in $Q; do blocal; run $V; done

# Denver baselines + zero-shot scores of everything above, once the Denver dataset exists (data pipeline: scripts/l3_0_data.sh)
while [ ! -f $DEN0 ]; do sleep 300; done
blocal
for V in $Q; do grep -q '^# l3-data: l3x' configs/generator_l3_$V.toml && X=l3x || X=; denver $V models/l3_$V.pt models/l3_$V.calib2021.npz $X; done
log all "queue done"
