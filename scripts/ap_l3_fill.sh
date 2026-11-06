#!/bin/bash
# After the lean loop-3 queue: rescore the Denver zero-shot of each candidate on the fill-top Denver set
# (L3-25 showed the old set left out the 23 % mountain rows and flattered every Denver number).
# Baseline is p2f on the same set (models/l3_braw_fill_cal2021_headline.csv). One GPU job at a time.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/denver_full_fill_dpd.npz B=models/l3_braw_fill_cal2021_headline.csv
log() { echo "$(date '+%F %T') [L3 fill] $*" >> data/l3.log; }
log start
while powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_lean|ap_l3.sh' }).Count" | tr -d '\r' | grep -qv '^0$'; do sleep 120; done
[ -f $D ] && [ -f $B ] || { log "no fill set or baseline"; exit 1; }
for V in siren w768 terrain ctxsep sirenw15 studt; do
  M=models/l3_$V.pt C=models/l3_$V.calib2021.npz; [ -f $M ] && [ -f $C ] || continue
  DATA=$D
  if grep -q '^# l3-data: l3x' configs/generator_l3_$V.toml 2>/dev/null; then
    DATA=${D%.npz}_l3x.npz
    [ -f $DATA ] || PYTHONPATH=. $PY -W ignore scripts/l3_overlay.py $D $DATA >> data/l3_overlay_denver.log 2>&1 || { log $V "FAILED fill overlay"; continue; }
  fi
  DM=models/l3_${V}_denfill.pt; cp $M $DM
  [ -f models/l3_${V}_denfill_cal2021_headline.csv ] || $PY -W ignore -u -m tempest.scoring.score --model $DM --data $DATA --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/l3_score_${V}_denfill.log 2>&1 || { log $V "FAILED fill score"; continue; }
  { echo "== $(date '+%F %T') DENVER fill-top zero-shot $V vs p2f"; $PY scripts/compare_headline.py $B models/l3_${V}_denfill_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
  log $V "fill scored"
done
log done
