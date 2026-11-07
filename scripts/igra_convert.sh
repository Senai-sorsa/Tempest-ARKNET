#!/bin/bash
# Converts the IGRA2 plain files once (tempest.ingest.igra_to_heights: 44 model heights + the A1 19-80 km grid, all
# launch hours, 1991-2025) as soon as scripts/fetch_chain.sh has finished its IGRA step, then deletes each raw zip after
# its npz is written (re-downloadable). CPU only, 4 workers at the 12-thread low-priority cap; never touches 2026.
# Log: data/igra_convert.log (+ a line in data/fetch_chain.log). Resumes: stations with an npz are skipped.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') $1" >> data/fetch_chain.log; }
until grep -qE "igra done|igra finished" data/fetch_chain.log; do sleep 600; done
log "igra convert start"
for try in 1 2; do
  .venv/Scripts/python -W ignore -u -m tempest.ingest.igra_to_heights --workers 4 --delete-raw >> data/igra_convert.log 2>&1 \
    && ! grep -q FAILED data/igra_convert.log && { log "igra convert done ($(ls data/igra_heights/*.npz | wc -l) stations)"; exit 0; }
  log "igra convert try $try had failures (see data/igra_convert.log)"
done
