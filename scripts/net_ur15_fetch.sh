#!/bin/bash
# UR15 (New_Plan 17.2): fetch ECMWF open-data HRES 2023-24 for both boxes, then build the rows. Network only (resumable: finished pieces are kept).
# User go 2026-11-14 ("try to fetch it if possible"). Launch: nohup bash scripts/net_ur15_fetch.sh > /dev/null 2>&1 &   Log: data/l3.log [UR15F]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [UR15F] $*" >> data/l3.log; }
log start
for b in nmtx denver; do
  $PY -W ignore -u scripts/ur15_opendata.py fetch $b --with-older > data/ur15_fetch_$b.log 2>&1 || { log "FAILED fetch $b"; continue; }
  log "fetch $b done"
  $PY -W ignore -u scripts/ur15_opendata.py rows $b > data/ur15_rows_$b.log 2>&1 && log "rows $b done" || log "FAILED rows $b"
done
log done
