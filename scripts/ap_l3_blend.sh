#!/bin/bash
# L14c / IL-161: blended-rank shuffle. The l21 stack (calibration + own shear map + shuffle c8) scored with --shuffle-w 0.5 and 0.75 (template ranks x w + the network's own order x (1 - w)), DAY seed 0, --mc,
# compared with the plain shuffle (w = 1: models/l3_s21l21_s0): headline rules and the physics rows. Model copies carry the run names. Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz BASE=models/l3_s21l21_s0_cal2021_smap_shufc8
log() { echo "$(date '+%F %T') [BLEND] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!blend)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $B.pt $CAL $SM ${BASE}_headline.csv ${BASE}_mc.csv; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
for W in 50 75; do
  M=models/l3_blend$W; cp $B.pt $M.pt; S=${M}_cal2021_smap_shufc8
  if [ ! -f ${S}_mc.csv ]; then
    for try in 1 2; do
      wait_gpu
      $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $CAL --shuffle --shuffle-w 0.$W --template-cell 8 --shear-map $SM > data/l3_blend$W.log 2>&1 && [ -f ${S}_mc.csv ] && { log "blend $W scored"; break; }
    done
  fi
  [ -f ${S}_mc.csv ] || { log "blend $W FAILED"; continue; }
  { echo "== $(date '+%F %T') L14c IL-161 shuffle weight 0.$W vs plain shuffle (DAY seed 0)"; $PY scripts/compare_headline.py ${BASE}_headline.csv ${S}_headline.csv
    echo "physics rows (w 1 | w 0.$W):"; grep -E "^phys" ${BASE}_mc.csv | sed 's/^/  w1 /'; grep -E "^phys" ${S}_mc.csv | sed "s/^/  w0.$W /"
    echo "coherence rows:"; grep -E "variogram|vcorr|es_skill_vs_clim15,all" ${BASE}_mc.csv | sed 's/^/  w1 /'; grep -E "variogram|vcorr|es_skill_vs_clim15,all" ${S}_mc.csv | sed "s/^/  w0.$W /"; } >> data/l3_verdicts.txt 2>&1
done
log done
