#!/bin/bash
# AV29 (New_Plan 13, variation of AV28): score the 12 AV28 networks (models/modeF_n2ft500{,_den}_s{0,1,2}.pt, modeF_n2own500...) on 2021 too
# (--test-year 2021: range map on 2022; no training) to pool with their 2022 rows. Outputs models/*_t2021_* (new files only).
# One evaluation at a time (20-24 GB RAM peak). Launch after SIGMA stage 2: nohup bash scripts/cpu_av29.sh &  Log: data/l3.log [AV29]. Verdict: new_plan_kit/b19_av29_pooled.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV29] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --test-year 2021"
log "start"
for S in 0 1 2; do
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    for arm in "ft500:--no-place" "own500:"; do
      name=${arm%%:*}$tag\_s$S; net=models/modeF_n2$name.pt
      [ -f models/modeF_n2${name}_t2021_rows.npz ] && { log "$name exists, skipped"; continue; }
      [ -f $net ] || { log "FAILED $name: no AV28 network"; continue; }
      while [ "$(powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -lt 15 ]; do sleep 60; done
      $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows ${arm##*:} $R --seed $S --out $net > data/av29_$name.log 2>&1 && log "$name done" || log "FAILED $name"
    done
  done
done
log done
