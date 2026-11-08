#!/bin/bash
# L3-45 NM/TX stack on 21 levels. L3-44 (23:04 Nov 7): l3_h_l21 beats l3_h_all24 on the 21-level truth, day +0.0257 -> +0.0281,
# night +0.0236 -> +0.0292 (gain in 0-1 km T / RH / v). Rebuild the NM/TX stack (calib + own shear map + shuffle c8, --mc, as
# L3-42) on l3_h_l21 and score it against the all24 stack, both on the 21-level files (same truth, same rows):
#   DAY   seeds 0/1/2 paired;  NIGHT seed 0
# Denver stays on all24 (no boundary-layer fill there; L3-44 zero-shot -0.1752 -> -0.2190 on the 13-level Denver truth).
# One GPU job at a time, waits for no other loop-3 queue, no GPU/build job and >= 9 GB free RAM. Every step skips when its
# output exists. Log: data/l3.log [L3-45]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz A21=data/train/pilot80_l21_all24_dpd.npz
A=models/l3_h_all24 CA=$A.calib2021.npz SMA=$A.shearmap2021_cell8.npz
L=models/l3_h_l21 CL=$L.calib2021.npz SML=$L.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [L3-45] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!l21stack)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 9 ]; do sleep 60; done; }

for f in $DA $NI $A21 $L.pt $CL $A.pt $CA $SMA; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
log "waiting for the loop-3 queue, GPU and builds"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 120; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
log start

# 1. own shear map for l3_h_l21 (as L3-40 fitted l3_h_all24's: NM/TX all hours, shuffle, full, template cell 8)
if [ ! -f $SML ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.shear_map --model $L.pt --data $A21 --calib $CL --shuffle --full --template-cell 8 \
      --out $SML > data/l3_l21stack_smap.log 2>&1 && { log "l21 shear map fitted"; break; }
    log "shear map try $try failed"
  done
  [ -f $SML ] || { log "FAILED shear map twice"; exit 2; }
fi

# 2. scores (copies carry run names so headline files never collide)
H() { echo models/$1_cal2021_smap_shufc8_headline.csv; }
run() {  # run STEM SRC DATA SEED CALIB SHEARMAP
  local M=models/$1.pt; cp $2 $M; [ -f $(H $1) ] && return 0; wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $4 \
    --calib $5 --shuffle --template-cell 8 --shear-map $6 > data/l3_l21stack_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; return 1; }
}
verdict() { [ -f $(H $1) ] && [ -f $(H $2) ] && { echo "== $(date '+%F %T') L3-45 $3"; $PY scripts/compare_headline.py $(H $1) $(H $2); } >> data/l3_verdicts.txt 2>&1; }
for s in 0 1 2; do
  run l3_s24l21_s$s $A.pt $DA $s $CA $SMA
  run l3_s21l21_s$s $L.pt $DA $s $CL $SML
  verdict l3_s24l21_s$s l3_s21l21_s$s "NM/TX l21 stack vs all24 stack DAY seed $s (21-level truth)"
done
run l3_s24l21_night $A.pt $NI 0 $CA $SMA
run l3_s21l21_night $L.pt $NI 0 $CL $SML
verdict l3_s24l21_night l3_s21l21_night "NM/TX l21 stack vs all24 stack NIGHT (21-level truth)"
log done
