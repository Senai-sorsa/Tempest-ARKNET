#!/bin/bash
# Waits for the Phase 2 variant runs to finish (one GPU job at a time), then trains and evaluates the vertical-wind head.
# Log: data/whead.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
log() { echo "$(date '+%F %T') $*" >> data/whead.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights' }).Count" | tr -d '\r'; }
until grep -q "phase2 p2cs1 done\|\[p2cs1\] FAILED" data/phase2.log; do sleep 60; done
while [ "$(busy)" != "0" ]; do sleep 30; done
log start
PYTHONPATH=. $PY -u scripts/whead.py train --data data/train/pilot80_dpd.npz --w data/train/pilot80_w.npz --out models/whead.pt > data/whead_train.log 2>&1 || { log "FAILED train"; exit 1; }
log trained
PYTHONPATH=. $PY -W ignore -u scripts/whead.py eval --model models/generator_80_p2c.pt --calib models/generator_80_p2c.calib2021.npz --data data/train/pilot80_dpd.npz --w data/train/pilot80_w.npz --head models/whead.pt > data/whead_eval.log 2>&1 || { log "FAILED eval"; exit 2; }
log "whead done"
