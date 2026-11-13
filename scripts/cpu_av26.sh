#!/bin/bash
# AV26 (New_Plan 13, variation of AV24): score the AV24 mix networks (models/av24_mix{,_den}{,_s1}.pt) on 2021 too (--test-year 2021: range map on mixed
# 2022; no training), to pool with 2022 against the newest-run networks' AV1 2021 scores. Outputs models/av24_mix*_t2021_* (new files only).
# One evaluation at a time (14-17 GB RAM peak). Launch: nohup bash scripts/cpu_av26.sh &  Log: data/l3.log [AV26]. Verdict: new_plan_kit/b13_av26.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV26] $*" >> data/l3.log; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
log "start"
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in ":nmtx" "_den:denver"; do
    tag=${box%%:*}; b=${box##*:}; name=mix$tag$sfx
    [ -f models/av24_${name}_t2021_rows.npz ] && { log "$name exists, skipped"; continue; }
    [ -f models/av24_$name.pt ] || { log "FAILED $name: no AV24 network"; continue; }
    while [ "$(powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -lt 15 ]; do sleep 60; done
    $PY -W ignore -u scripts/il6_modeF.py --rows-dir data/chorus_${b}_mixall $SMALL --seed $S --test-year 2021 --out models/av24_$name.pt > data/av26_$name.log 2>&1 && log "$name done" || log "FAILED $name"
  done
done
log done
