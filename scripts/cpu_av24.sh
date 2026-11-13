#!/bin/bash
# AV24 (New_Plan 13, variation of CHORUS stage 1): the stage 1 closed-rule mix (same 2018-20 weights) in EVERY year's rows
# (scripts/chorus_stage1_rows.py <box> --all-years -> data/chorus_<box>_mixall), mode F RETRAINED on the mixed rows with the shipped small recipe
# (same flags and seeds as models/modeF_n2_base*), PIT recal and range map on mixed 2021, scored on mixed 2022 (= the stage 1 test rows).
# Compared with the stage 1 newest-run scores (models/chorus_new*_rows.npz, same rows). New files only: models/av24_mix<tag><sfx>.*.
# One evaluation at a time (14-17 GB RAM peak). Launch: nohup bash scripts/cpu_av24.sh &  Log: data/l3.log [AV24]; per run data/av24_<name>.log.
# Verdict: new_plan_kit/b12_av24.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV24] $*" >> data/l3.log; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
log "start"
for b in nmtx denver; do
  [ -f data/chorus_${b}_mixall/2021.npz ] && [ -f data/chorus_${b}_mixall/2022.npz ] && { log "rows $b exist, skipped"; continue; }
  $PY -W ignore -u scripts/chorus_stage1_rows.py $b --all-years > data/av24_rows_$b.log 2>&1 && log "rows $b done" || { log "FAILED rows $b"; exit 1; }
done
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in ":nmtx" "_den:denver"; do
    tag=${box%%:*}; b=${box##*:}; name=mix$tag$sfx
    [ -f models/av24_${name}_rows.npz ] && { log "$name exists, skipped"; continue; }
    while [ "$(powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -lt 15 ]; do sleep 60; done
    $PY -W ignore -u scripts/il6_modeF.py --rows-dir data/chorus_${b}_mixall $SMALL --seed $S --out models/av24_$name.pt > data/av24_$name.log 2>&1 && log "$name done" || log "FAILED $name"
  done
done
log done
