#!/bin/bash
# Lean loop-3 queue (user 2026-11-06: only the important runs + the Gemini fixes and ideas; the rest is sidelined, see docs/logs/LOOP3.md).
# Replaces ap_l3.sh's default queue, ap_l3_data.sh (D1-D7) and ap_l3_more.sh. One GPU job at a time.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [L3 lean] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|calibrate.joint|scoring' }).Count" | tr -d '\r'; }
log start
while [ "$(busy)" != "0" ]; do sleep 60; done            # w768 training (started by the old queue) finishes on its own
[ -f models/l3_w768.pt.part ] && [ ! -f models/l3_w768.pt ] && mv models/l3_w768.pt.part models/l3_w768.pt   # train saves .part only at the end
# 1. Denver with the mountain rows (Gemini A2): rebuild with --fill-top, rescore p2f zero-shot
D=data/train/denver_full_fill_dpd.npz
[ -f $D ] || { TEMPEST_REGION=configs/region_denver.toml CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles data/pilot/profiles_denver_full.zarr --out $D.part --rows 4000000 --first-year 1991 --last-year 2025 --station-map models/station_map_denver_full.npz --features base --rh-target dpd --fill-top >> data/l3_build_fill.log 2>&1 && mv $D.part $D; } || log "FAILED fill build"
if [ -f $D ]; then
  log "denver fill built"
  M=models/l3_braw_fill.pt; cp -n models/generator_80_p2f.pt $M
  [ -f models/l3_braw_fill_cal2021_headline.csv ] || $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/generator_80_p2f.calib2021.npz --extras > data/l3_score_braw_fill.log 2>&1 || log "FAILED fill score"
  { echo "== $(date '+%F %T') DENVER p2f zero-shot: with mountain rows (fill-top) vs without"; $PY scripts/compare_headline.py models/l3_braw_cal2021_headline.csv models/l3_braw_fill_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
fi
# 2. w768 (already trained), terrain (most important feature for new places), Gemini fixes ctxsep/sirenw15, Gemini ideas studt/jump
bash scripts/ap_l3.sh w768 terrain ctxsep sirenw15 studt jump
log done
