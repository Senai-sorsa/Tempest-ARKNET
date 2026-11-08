#!/bin/bash
# L14a pre-check: the stage audit (seed 0) said calibration raises the surface-jump row 0.0018 -> 0.0046, but the full stack at seeds 1, 2 has jump rows near ERA5 (0.0012). Repeat stages A (raw) and B (calibrated) on seeds 1 and 2 to see whether the calibration jump is real or a seed-0 sampling effect.
#   A raw network   B + range calibration   C + shear map   E + calibration + shuffle (no shear map)   D = full stack (existing models/l3_s21l21_s0 mc.csv)
# Copies of the model carry stage names so nothing collides. Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM; skips finished stages. Log: data/l3.log [AUDIT2]; verdicts: data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [AUDIT2] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!stageaudit2)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $B.pt $CAL $SM models/l3_s21l21_s0_cal2021_smap_shufc8_mc.csv; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
stage() {  # stage NAME SEED SUFFIX ARGS...
  local n=$1 sd=$2 suf=$3; shift 3
  local M=models/l3_aud2_$n; cp $B.pt $M.pt
  [ -f ${M}${suf}_mc.csv ] && return 0
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $sd "$@" > data/l3_aud2_$n.log 2>&1 && [ -f ${M}${suf}_mc.csv ] && { log "stage $n done"; return 0; }
  done
  log "stage $n FAILED"; return 1
}
stage A_s1 1 ""; stage B_s1 1 "_cal2021" --calib $CAL; stage A_s2 2 ""; stage B_s2 2 "_cal2021" --calib $CAL
{ echo "== $(date '+%F %T') L14a pre-check: surface-jump row (ERA5 about 0.0010) raw vs calibrated on seeds 1 and 2 (seed 0 was 0.0018 -> 0.0046)"
  for f in models/l3_aud2_A_s1_mc.csv models/l3_aud2_B_s1_cal2021_mc.csv models/l3_aud2_A_s2_mc.csv models/l3_aud2_B_s2_cal2021_mc.csv; do echo "-- $f"; [ -f $f ] && grep -E "^phys" $f || echo "   (missing)"; done; } >> data/l3_verdicts.txt
log done
