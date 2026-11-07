#!/bin/bash
# L3-39: is the all24 DAY result (+0.0278 vs p2f +0.0277, seed 0) real across held-out row draws? Scores all24 on the
# NM/TX day file with seeds 0/1/2 using the same flags as the p2f seed baselines (models/g9_p2f_nmtx{,_s1,_s2}), and
# compares each pair (same seed = same 5,000 held-out rows). No retrain. Runs after scripts/ap_l3_hours.sh logs done.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
M=models/l3_h_all24 C=models/l3_h_all24.calib2021.npz NX=data/train/pilot80_dpd.npz G=models/g9_p2f_nmtx
log() { echo "$(date '+%F %T') [L3-39] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
until grep -q "\[HOURS all\] done" data/l3.log; do sleep 120; done
sleep 90
while [ "$(busy)" != "0" ]; do sleep 60; done
log start
for s in 0 1 2; do
  T=${M}_seed$s; [ $s = 0 ] && B=$G || B=${G}_s$s
  cp $M.pt $T.pt
  [ -f ${T}_cal2021_headline.csv ] || $PY -W ignore -u -m tempest.scoring.score --model $T.pt --data $NX --m 199 --first-test-year 2024 \
    --last-test-year 2025 --mc --calib $C --seed $s > data/l3_score_h_seed$s.log 2>&1 || { log "FAILED seed $s"; continue; }
  { echo "== $(date '+%F %T') L3-39 all24 DAY seed $s vs p2f seed $s"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${T}_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
  log "seed $s scored"
done
log done
