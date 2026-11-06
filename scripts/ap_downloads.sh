#!/bin/bash
# "Downloads to do.md" A2, A3, A1 (A4 GFS-on-AWS is not run: about 160 GB of transfer). One download at a time, each only when no heavy local job (training, scoring, dataset build, diagnostics) is running,
# low network rate. New folders only, existing data/raw folders are never touched. Resumable: every script skips what exists. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|scoring|build_dataset|to_heights|diagnose|calibrate' }).Count" | tr -d '\r'; }
wait_idle() { for i in $(seq 1 15); do [ "$(busy)" = "0" ] && return; sleep 120; done; }   # wait up to 30 minutes for a quiet moment, then go ahead: the downloads are light (network, a few hundred MB), starving them would help nobody
log() { echo "$(date '+%F %T') $*" >> data/ap_downloads.log; }
wait_idle; log "A2 asos start"
PYTHONPATH=. $PY -u -m tempest.ingest.fetch_asos --out data/raw/asos_2026 --first 2024 --last 2026 >> data/ap_downloads_asos.log 2>&1 && log "A2 asos done" || log "A2 asos FAILED"
wait_idle; log "A3 igra start"
PYTHONPATH=. $PY -u -m tempest.ingest.fetch_igra --out data/raw/igra_2026 >> data/ap_downloads_igra.log 2>&1 && log "A3 igra pilot done" || log "A3 igra pilot FAILED"
wait_idle
PYTHONPATH=. $PY -u -m tempest.ingest.fetch_igra --out data/raw/igra_denver_2026 USM00072469 >> data/ap_downloads_igra.log 2>&1 && log "A3 igra denver done" || log "A3 igra denver FAILED"
wait_idle; log "A1 previous runs start"
PYTHONPATH=. $PY -u scripts/fetch_previous_runs.py >> data/ap_downloads_prev.log 2>&1 && log "A1 previous runs done" || log "A1 previous runs FAILED"
log "downloads chain done"
