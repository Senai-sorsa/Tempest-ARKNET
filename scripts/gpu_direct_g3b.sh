#!/bin/bash
# G3b (2026-11-09): do per-point shuffle templates restore the wind-shear co-extremes (balloons 0.17, tool 0.07)? The shipped stack (generator_80_c4w + calibration + shear map +
# lapse map) scored on data/train/pilot80_dpd.npz, DAY 2024-25, seed 0, --mc (the physics rows now include the co-extreme row, model vs the ERA5 truth rows), with
# (a) --template-cell 8 (shipped 2-degree block templates), (b) --template-cell 0 (per-point templates), (c) no shuffle (floor). One runner (B27); waits for >= 8 GB free RAM.
# Log: data/l3.log [G3B]; results: the coextreme and headline rows are summarised into data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz M=models/generator_80_c4w
log() { echo "$(date '+%F %T') [G3B] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
log start
for spec in "g3b_c8 --shuffle --template-cell 8" "g3b_c0 --shuffle --template-cell 0" "g3b_noshuf"; do
  set -- $spec; S=models/$1; [ -f $S.pt ] || cp $M.pt $S.pt; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model $S.pt --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $M.calib2021.npz "${@:2}" \
    --shear-map $M.shearmap2021_cell8.npz --lapse-map $M.lapsemap2021.npz > data/l3_g3b_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
done
{ echo "== $(date '+%F %T') G3B co-extremes (model | ERA5 truth rows) and headline, shipped stack, templates per 2-degree block / per point / no shuffle"
  for f in models/g3b_*_mc.csv; do echo "  $f"; grep coextreme $f | sed 's/^/    /'; done
  $PY scripts/compare_headline.py $(ls models/g3b_c8_*headline.csv) $(ls models/g3b_c0_*headline.csv) | grep -E "mean skill|rule|PHASE"; } >> data/l3_verdicts.txt 2>&1
log done
