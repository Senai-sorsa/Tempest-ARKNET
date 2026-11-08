#!/bin/bash
# L14d / IL-162: lapse-rate quantile map. Fit on 2021-23 samples that went through calibration, shuffle (c8) and the shear map, then score the l21 stack with --lapse-map (DAY seed 0, --mc) and compare with the
# plain stack (models/l3_s21l21_s0): headline rules and the physics rows (superadiabatic 0.324 -> toward 0.199, shear 0.0145, surface jump 0.0027). Waits for no other loop-3 queue, no GPU/build job, >= 6 GB RAM. Log: data/l3.log [LAPSE].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz BASE=models/l3_s21l21_s0_cal2021_smap_shufc8
M=models/l3_lapse LM=models/l3_lapse.lapsemap2021.npz
log() { echo "$(date '+%F %T') [LAPSE] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!lapse)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $A21 $DA $B.pt $CAL $SM ${BASE}_headline.csv ${BASE}_mc.csv; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
cp $B.pt $M.pt
if [ ! -f $LM ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.lapse_map --model $M.pt --data $A21 --calib $CAL --shear-map $SM --shuffle --template-cell 8 --out $LM > data/l3_lapse_fit.log 2>&1 && [ -f $LM ] && { log "lapse map fitted"; break; }
  done
  [ -f $LM ] || { log "FAILED lapse fit"; exit 5; }
fi
S=${M}_cal2021_smap_shufc8_lmap
if [ ! -f ${S}_mc.csv ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $CAL --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/l3_lapse_score.log 2>&1 && [ -f ${S}_mc.csv ] && { log "lapse scored"; break; }
  done
fi
[ -f ${S}_mc.csv ] || { log "FAILED lapse score"; exit 6; }
{ echo "== $(date '+%F %T') L14d IL-162 lapse map vs plain l21 stack (DAY seed 0)"; $PY scripts/compare_headline.py ${BASE}_headline.csv ${S}_headline.csv
  echo "fit log:"; cat data/l3_lapse_fit.log | tail -8
  echo "physics rows (base | lmap):"; grep -E "^phys" ${BASE}_mc.csv | sed 's/^/  base /'; grep -E "^phys" ${S}_mc.csv | sed 's/^/  lmap /'; } >> data/l3_verdicts.txt 2>&1
log done
