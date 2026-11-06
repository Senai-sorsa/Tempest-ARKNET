#!/bin/bash
# Extra data, chained after the global store (docs/DATA_NEEDS.md, user request 2026-11-06), one download at a time
# (they share the home link): global extras -> IGRA plain files -> 6 G2 boxes. Every step resumes/skips what exists.
# Log: data/fetch_chain.log (+ each step's own log). CPU/network only, runs beside the GPU queue.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=".venv/Scripts/python -W ignore -u -m"
log() { echo "$(date '+%F %T') $1" >> data/fetch_chain.log; }
retry() {  # retry N CMD... : rerun a resumable step after a crash, at most N times
  local n=$1; shift
  for i in $(seq $n); do "$@" && return 0; log "step failed ($*), retry $i/$n in 5 min"; sleep 300; done
  return 1
}
log "waiting for fetch_global done"
until grep -q "fetch_global done" data/global_fetch.log; do sleep 300; done
log "extras start"; retry 20 $PY tempest.ingest.fetch_global_extra >> data/global_extra.log 2>&1 && log "extras done" || log "extras FAILED"
log "igra start"; retry 2 $PY tempest.ingest.fetch_igra_data >> data/igra_data.log 2>&1 && log "igra done" || log "igra finished with failures (see data/igra_data.log)"
for b in vandenberg canaveral fairbanks saltlake lamont hilo; do
  [ -f data/raw/era5_g2_$b/DONE ] && continue
  log "g2 $b start"
  if TEMPEST_REGION=configs/region_g2_$b.toml CUDA_VISIBLE_DEVICES=-1 retry 5 $PY tempest.ingest.fetch_earthmover --out data/raw/era5_g2_$b --first 1991 --last 2025-12-31 --workers 4 >> data/g2_fetch.log 2>&1; then
    touch data/raw/era5_g2_$b/DONE; log "g2 $b done"
  else log "g2 $b FAILED"; fi
done
log "chain done"
