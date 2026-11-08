#!/bin/bash
# L14d confirmation: the lapse map (models/l3_lapse.lapsemap2021.npz, fitted once) scored on DAY seeds 1 and 2 and NIGHT seed 0, each paired with the existing plain l21 stack of the same seed and data
# (models/l3_s21l21_{s1,s2,night}). Verdict rows to data/l3_verdicts.txt. Waits for no other loop-3 queue, no GPU/build job, >= 6 GB RAM. Log: data/l3.log [LAPSE2].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz LM=models/l3_lapse.lapsemap2021.npz
log() { echo "$(date '+%F %T') [LAPSE2] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!lapse2)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $NI $B.pt $CAL $SM $LM; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
run() {  # run NAME BASE_STEM DATA SEED
  local M=models/l3_lapse_$1; cp $B.pt $M.pt
  local S=${M}_cal2021_smap_shufc8_lmap BASE=models/l3_s21l21_$2_cal2021_smap_shufc8
  if [ ! -f ${S}_mc.csv ]; then
    for try in 1 2; do
      wait_gpu
      $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $4 --calib $CAL --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/l3_lapse2_$1.log 2>&1 && [ -f ${S}_mc.csv ] && { log "$1 scored"; break; }
    done
  fi
  [ -f ${S}_mc.csv ] && [ -f ${BASE}_mc.csv ] || { log "$1 FAILED or base missing"; return; }
  { echo "== $(date '+%F %T') L14d IL-162 lapse map vs plain stack, $1"; $PY scripts/compare_headline.py ${BASE}_headline.csv ${S}_headline.csv | grep -E "mean skill|rule|PHASE|mean \|"
    grep -E "^phys" ${BASE}_mc.csv | sed 's/^/  base /'; grep -E "^phys" ${S}_mc.csv | sed 's/^/  lmap /'; } >> data/l3_verdicts.txt 2>&1
}
run s1 s1 $DA 1; run s2 s2 $DA 2; run night night $NI 0
log done
