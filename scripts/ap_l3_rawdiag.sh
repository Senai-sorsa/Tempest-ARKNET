#!/bin/bash
# LOOP3 L3-31/L3-32: raw (uncalibrated) p2f scored with --mc at NM/TX and on the fill-top Denver set. Its phys rows
# (surface jump, superadiabatic) and derived rows (inversion step < 3 km) vs the calibrated G9 p2f rows say whether the
# per-column range calibration causes the surface jumps and the Denver inversion miss. Model copies l3_p2fraw*.pt keep
# every existing score file untouched. Waits for the L3-30 runner, then for an idle GPU and >= 9 GB free RAM.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [L3-31] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() { while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring.score')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 120; done; }
while [ "$(nproc_match bash.exe 'ap_l3_trustdi|ap_l3_studtclip')" != "0" ]; do sleep 120; done
log start
for S in nmtx den; do
  [ $S = nmtx ] && D=data/train/pilot80_dpd.npz || D=data/train/denver_full_fill_dpd.npz
  G=models/l3_p2fraw_$S.pt
  cp models/generator_80_p2f.pt $G
  wait_room
  $PY -W ignore -u -m tempest.scoring.score --model $G --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc > data/l3_score_p2fraw_$S.log 2>&1 \
    && log "raw $S scored" || log "FAILED raw $S score"
done
log done
