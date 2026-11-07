#!/bin/bash
# L3-41: the L3-40 Denver all24 stack lost -0.0004 by day on seed 0 (tolerance 0.0006, the seed's held-out rows alone span
# 0.0025), so day is re-scored on seeds 1 and 2 for both stacks (paired, same held-out rows), as L3-39 did for NM/TX.
# Model copies carry the seed in their name so headline files never collide. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz
log() { echo "$(date '+%F %T') [L3-41] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 9 ]; do sleep 60; done; }
run() {  # run STEM SRC SEED CALIB TRUST SHEARMAP
  local M=models/$1.pt H=models/$1_cal2021_trust_smap_shufc8_headline.csv
  cp $2 $M; [ -f $H ] && return 0; wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 \
    --calib $4 --trust $5 --shuffle --template-cell 8 --shear-map $6 > data/l3_denseed_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; return 1; }
}
log start
for s in 1 2; do
  run l3_p2fden_s$s models/l3_p2fden_fx.pt $s models/generator_80_p2f.calib2021.npz models/l3_p2fden.trust2021.npz models/generator_80_p2f.shearmap2021_cell8.npz
  run l3_a24den_s$s models/l3_a24den.pt $s models/l3_h_all24.calib2021.npz models/l3_a24den.trust2021.npz models/l3_h_all24.shearmap2021_cell8.npz
  { echo "== $(date '+%F %T') L3-41 DENVER all24 stack DAY seed $s vs p2f stack seed $s"
    $PY scripts/compare_headline.py models/l3_p2fden_s${s}_cal2021_trust_smap_shufc8_headline.csv models/l3_a24den_s${s}_cal2021_trust_smap_shufc8_headline.csv; } >> data/l3_verdicts.txt 2>&1
done
log done
