#!/bin/bash
# IL-170 install (2026-11-10): after the running test suite finishes, copy the staged Denver day and all-hours sets (+ shuffle templates c8 from the full-grid all-hours file, shear map,
# lapse map, Denver mode F) into tempest_weather/assets_denver and assets_denver_allhours, then run the end-to-end audit. Previous versions stay in models/assets_denver_modef_staging and
# models/assets_denver_allhours_modef_staging. Log: data/l3.log [DENPOST]; audit output data/tool_audit_run3.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [DENPOST] $*" >> data/l3.log; }
until grep -q 'TESTS\] done after A24fix' data/l3.log; do sleep 30; done
cp models/assets_denver_post_staging/{model.npz,indices.npz,grid.npz,manifest.json} tempest_weather/assets_denver/ && \
cp models/assets_denver_allhours_post_staging/{model.npz,indices.npz,grid.npz,manifest.json} tempest_weather/assets_denver_allhours/ && log installed || { log "FAILED install"; exit 1; }
PYTHONPATH=. .venv/Scripts/python -W ignore scripts/tool_audit.py --rows 120 > data/tool_audit_run3.log 2>&1 && log "audit done" || log "FAILED audit"
