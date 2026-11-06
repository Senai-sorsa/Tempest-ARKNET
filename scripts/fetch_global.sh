#!/bin/bash
# Global G4 point store (tempest/ingest/fetch_global.py), resumable; CPU/network only, runs beside the GPU queue.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
until .venv/Scripts/python -W ignore -u -m tempest.ingest.fetch_global >> data/global_fetch.log 2>&1; do
  echo "$(date '+%F %T') fetch_global exited with an error, retrying in 5 min" >> data/global_fetch.log; sleep 300
done
echo "$(date '+%F %T') fetch_global done" >> data/global_fetch.log
