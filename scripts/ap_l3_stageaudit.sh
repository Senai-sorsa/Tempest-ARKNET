#!/bin/bash
# L14b / IL-160: which stage of the calibration stack adds the physics excess (surface jump, shear tail, superadiabatic)? One model (l3_h_l21), DAY seed 0, 2024-25, --mc after each stage:
#   A raw network   B + range calibration   C + shear map   E + calibration + shuffle (no shear map)   D = full stack (existing models/l3_s21l21_s0 mc.csv)
# Copies of the model carry stage names so nothing collides. Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM; skips finished stages. Log: data/l3.log [AUDIT]; verdicts: data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz B=models/l3_h_l21 CAL=models/l3_h_l21.calib2021.npz SM=models/l3_h_l21.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [AUDIT] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!stageaudit)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $B.pt $CAL $SM models/l3_s21l21_s0_cal2021_smap_shufc8_mc.csv; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
stage() {  # stage NAME EXPECTED_MC_SUFFIX ARGS...
  local n=$1 suf=$2; shift 2
  local M=models/l3_aud_$n; cp $B.pt $M.pt
  [ -f ${M}${suf}_mc.csv ] && return 0
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 "$@" > data/l3_aud_$n.log 2>&1 && [ -f ${M}${suf}_mc.csv ] && { log "stage $n done"; return 0; }
  done
  log "stage $n FAILED (see data/l3_aud_$n.log)"; return 1
}
stage A_raw "" 
stage B_cal "_cal2021" --calib $CAL
stage C_smap "_cal2021_smap" --calib $CAL --shear-map $SM
stage E_shuf "_cal2021_shufc8" --calib $CAL --shuffle --template-cell 8
{ echo "== $(date '+%F %T') L14b IL-160 stage audit, physics rows (superadiabatic_gt1K ERA5 0.199 | shear_gt_era5_9999 0.0082 | sfc_jump_gt_era5_999 0.0010)"
  for f in models/l3_aud_A_raw_mc.csv models/l3_aud_B_cal2021_mc.csv models/l3_aud_C_smap_cal2021_smap_mc.csv models/l3_aud_E_shuf_cal2021_shufc8_mc.csv models/l3_s21l21_s0_cal2021_smap_shufc8_mc.csv; do
    echo "-- $f"; [ -f $f ] && grep -E "^phys" $f || echo "   (missing)"; done; } >> data/l3_verdicts.txt
log done
