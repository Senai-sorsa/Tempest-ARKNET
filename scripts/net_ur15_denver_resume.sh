#!/bin/bash
# UR15F resume (Denver only; nmtx already done). Appends to the logs. Log: data/l3.log [UR15F]
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [UR15F] $*" >> data/l3.log; }
log "resume denver"
$PY -W ignore -u scripts/ur15_opendata.py fetch denver --with-older >> data/ur15_fetch_denver.log 2>&1 || { log "FAILED fetch denver"; exit 1; }
log "fetch denver done"
$PY -W ignore -u scripts/ur15_opendata.py rows denver >> data/ur15_rows_denver.log 2>&1 && log "rows denver done" || log "FAILED rows denver"
log done
