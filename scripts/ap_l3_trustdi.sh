#!/bin/bash
# LOOP3 L3-29: DI-gated trust blend. L3-28 DI puts every Denver point far outside the NM/TX area of applicability
# (DI 21-36 vs threshold 2.5) and every NM/TX point inside (0), so the gate is binary here: NM/TX keeps p2f as is,
# Denver gets the trust layer fitted on Denver 2021-23 (scored on 2024-25). The model copy l3_p2fden keeps p2f's own
# trust2021 file untouched.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz C=models/generator_80_p2f.calib2021.npz M=models/l3_p2fden.pt
log() { echo "$(date '+%F %T') [L3-29] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() { while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring.score')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 120; done; }
log start
cp models/generator_80_p2f.pt $M
wait_room
$PY -W ignore -u -m tempest.calibrate.trust --model $M --data $DEN --calib $C --from-year 2021 --year 2023 --m 199 > data/l3_trustdi_fit.log 2>&1 \
  && log "trust fit on Denver 2021-23 done" || { log "FAILED trust fit"; exit 1; }
wait_room
$PY -W ignore -u -m tempest.scoring.score --model $M --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C \
  --trust ${M%.pt}.trust2021.npz --mc > data/l3_trustdi_score.log 2>&1 && log "Denver scored with trust" || log "FAILED Denver score"
log done
