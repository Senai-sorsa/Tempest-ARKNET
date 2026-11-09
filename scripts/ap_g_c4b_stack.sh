#!/bin/bash
# G-GPU / L21 input: C4b (near-ground wind loss, models/l3_c4b.pt, trained on the same 21-level all-hours data as l3_h_l21) has only been scored
# with the spread calibration alone (L8 verdict: speed MAE 0-1 km -1.3 %, T/RH 0-1 km slightly worse; three seeds never run). Put it through the
# CURRENT l21 stack recipe (own shear map: NM/TX all hours, shuffle, full, template cell 8; score --mc --shuffle --template-cell 8) and pair it with
# the l21 stack: DAY score seeds 0/1/2, NIGHT seed 0. No training. Verdicts: data/l3_verdicts.txt; log: data/l3.log [C4BS].
# Waits for no other queue, no GPU/build job and >= 6 GB free RAM; every step skips when its output exists, retried once. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
M=models/l3_c4b CM=$M.calib2021.npz SM=$M.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [C4BS] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights|pytest' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3|ap_g9|ap_g_(?!c4b_stack)' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
H() { echo models/$1_cal2021_smap_shufc8_headline.csv; }
for f in $A21 $DA $NI $M.pt $CM $(H l3_s21l21_s0) $(H l3_s21l21_s1) $(H l3_s21l21_s2) $(H l3_s21l21_night); do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
if [ ! -f $SM ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $A21 --calib $CM --shuffle --full --template-cell 8 --out $SM > data/l3_c4bs_smap.log 2>&1 && { log "shear map fitted"; break; }
    log "shear map try $try failed"
  done
  [ -f $SM ] || { log "FAILED shear map twice"; exit 2; }
fi
run() {  # run STEM DATA SEED
  local P=models/$1.pt; [ -f $P ] || cp $M.pt $P; [ -f $(H $1) ] && return 0
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $P --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 \
      --calib $CM --shuffle --template-cell 8 --shear-map $SM > data/l3_c4bs_$1.log 2>&1 && { log "$1 scored"; return 0; }
    log "$1 try $try failed"
  done
  log "FAILED $1"; return 1
}
verdict() { [ -f $(H $1) ] && [ -f $(H $2) ] && { echo "== $(date '+%F %T') C4B-STACK $3"; $PY scripts/compare_headline.py $(H $1) $(H $2)
  echo "physics rows (base | c4b):"; grep -E "superadiabatic|shear_gt|sfc_jump" models/$1_cal2021_smap_shufc8_mc.csv | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" models/$2_cal2021_smap_shufc8_mc.csv | sed 's/^/  c4b  /'; } >> data/l3_verdicts.txt 2>&1; }
for s in 0 1 2; do
  run l3_c4bs_s$s $DA $s
  verdict l3_s21l21_s$s l3_c4bs_s$s "C4b on the l21 stack vs l21 stack DAY seed $s"
done
run l3_c4bs_night $NI 0
verdict l3_s21l21_night l3_c4bs_night "C4b on the l21 stack vs l21 stack NIGHT"
log done
