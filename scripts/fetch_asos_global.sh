#!/bin/bash
# Worldwide gust truth (tempest/ingest/fetch_asos_global.py). Rate-limited, low bandwidth: runs in parallel with everything.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
for i in 1 2 3; do
  .venv/Scripts/python -W ignore -u -m tempest.ingest.fetch_asos_global >> data/asos_global.log 2>&1 && break
  echo "$(date '+%F %T') exited with an error, retry $i in 5 min" >> data/asos_global.log; sleep 300
done
echo "$(date '+%F %T') asos_global script end" >> data/asos_global.log
