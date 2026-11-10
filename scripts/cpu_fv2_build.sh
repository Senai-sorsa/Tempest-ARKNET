#!/bin/bash
# F-V2 build (CPU): mode F rows from the 00Z + 12Z refetch, NM/TX (data/modeF_v2) then Denver (data/modeF_v2_denver from wb2_hres_v2_denver + profiles_denver_full.zarr).
# Reads the ERA5 store, so it starts only when [A24] reaches the Denver TRAINING step (training holds less RAM; no store reads beside GPU scores, B28) and needs >= 8 GB free RAM.
# Log: data/l3.log [FV2]; output data/fv2_build.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [FV2] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
until grep -q '\[A24\] a24den_c4w train' data/l3.log; do sleep 60; done
while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done
log "build start"
PYTHONPATH=. $PY -W ignore -u scripts/il6_build_v2.py >> data/fv2_build.log 2>&1 && log "nmtx built" || log "FAILED nmtx build"
PYTHONPATH=. $PY -W ignore -u scripts/il6_build_v2.py --hres-dir data/raw/wb2_hres_v2_denver --store data/pilot/profiles_denver_full.zarr --out-dir data/modeF_v2_denver >> data/fv2_build.log 2>&1 && log "denver built" || log "FAILED denver build"
log "build done"
