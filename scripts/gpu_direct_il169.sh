#!/bin/bash
# IL-169 (2026-11-10): co-extreme ratio after each step of the shipped stack (scripts/g3b_coextreme_stages.py), seeds 0 and 1. Waits for [DENEXP] done (one GPU job, B27) and >= 10 GB free RAM.
# Log: data/l3.log [IL169]; output docs/results/logs/il169_coextreme_stages.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [IL169] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
until grep -q '\[DENEXP\] done' data/l3.log; do sleep 60; done
log start
OUT=docs/results/logs/il169_coextreme_stages.log
: > $OUT
for s in 0 1; do
  while [ "$(ram_gb)" -lt 10 ]; do sleep 60; done
  PYTHONPATH=. $PY -W ignore -u scripts/g3b_coextreme_stages.py --seed $s >> $OUT 2>&1 && log "seed $s done" || log "FAILED seed $s"
done
log done
