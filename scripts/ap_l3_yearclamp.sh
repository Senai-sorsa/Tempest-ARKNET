#!/bin/bash
# L14e: year clamp test. The l21 stack (calibration + own shear map + shuffle c8) scored on DAY seeds 0 and 1 with the year feature of the 2024-25 rows held at 2023 (--year-clamp 2023) with and without a pooled warming shift
# (+0.034 K per year for t2m and T up to 10 km, from the ERA5 backtest), against the plain stack of the same seed (models/l3_s21l21_s0 / s1). Verdict: headline rules and the t2m / T rows. Log [YCLAMP].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [YCLAMP] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!yearclamp)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $B.pt $CAL $SM; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
run() {  # run TAG SEED EXTRA...   output stem models/l3_yc_TAG_cal2021_smap_shufc8_yc2023[s0.034]
  local tag=$1 sd=$2; shift 2
  local M=models/l3_yc_$tag; cp $B.pt $M.pt
  local suf=_cal2021_smap_shufc8_yc2023; [[ "$*" == *"--year-shift"* ]] && suf=${suf}s0.034
  [ -f ${M}${suf}_mc.csv ] && return 0
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $sd --calib $CAL --shuffle --template-cell 8 --shear-map $SM "$@" > data/l3_yc_$tag.log 2>&1 && [ -f ${M}${suf}_mc.csv ] && { log "$tag scored"; return 0; }
  done
  log "$tag FAILED"
}
run s0clamp 0 --year-clamp 2023; run s0shift 0 --year-clamp 2023 --year-shift 0.034
run s1clamp 1 --year-clamp 2023; run s1shift 1 --year-clamp 2023 --year-shift 0.034
for sd in 0 1; do
  BASE=models/l3_s21l21_s${sd}_cal2021_smap_shufc8
  for v in clamp shift; do
    suf=_cal2021_smap_shufc8_yc2023; [ $v = shift ] && suf=${suf}s0.034
    S=models/l3_yc_s${sd}${v}${suf}
    [ -f ${S}_headline.csv ] && [ -f ${BASE}_headline.csv ] && { echo "== $(date '+%F %T') L14e year $v vs plain stack, DAY seed $sd"; $PY scripts/compare_headline.py ${BASE}_headline.csv ${S}_headline.csv | grep -E "t2m|^ *T  |mean skill|rule|PHASE"; } >> data/l3_verdicts.txt 2>&1
  done
done
log done
