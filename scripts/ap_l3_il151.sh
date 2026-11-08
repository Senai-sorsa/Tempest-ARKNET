#!/bin/bash
# L11 / IL-151: physics penalty experiment. p2f + superadiabatic_weight 0.01 (configs/generator_il151.toml) on the 21-level NM/TX data; the l21 stack recipe (calibrate, own shear map with shuffle and template cell 8, --mc) and the
# DAY seed-0 score are compared with models/l3_s21l21_s0 (same data, same seed): headline rules and the mc.csv physics rows (superadiabatic, shear tail, surface jump).
# Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM; every step skips when its output exists, retried once. Log: data/l3.log [IL151]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz
M=models/l3_il151 B=models/l3_s21l21_s0
log() { echo "$(date '+%F %T') [IL151] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!il151)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $A21 $DA ${B}_cal2021_smap_shufc8_headline.csv ${B}_cal2021_smap_shufc8_mc.csv configs/generator_il151.toml; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
if [ ! -f $M.pt ]; then
  for try in 1 2; do
    wait_gpu; log "train try $try"
    $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_il151.toml > data/l3_train_il151.log 2>&1 && mv $M.pt.part $M.pt && break
  done
  [ -f $M.pt ] || { log "FAILED train twice"; exit 4; }
fi
if [ ! -f $M.calib2021.npz ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_il151.log 2>&1 || { log "FAILED spread"; exit 4; }
fi
if [ ! -f $M.shearmap2021_cell8.npz ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $A21 --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_il151_smap.log 2>&1 && break
  done
  [ -f $M.shearmap2021_cell8.npz ] || { log "FAILED shear map"; exit 5; }
fi
H=${M}_s0_cal2021_smap_shufc8_headline.csv
if [ ! -f $H ]; then
  cp $M.pt ${M}_s0.pt; wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model ${M}_s0.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $M.calib2021.npz --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz > data/l3_score_il151.log 2>&1 && log "il151 scored" || { log "FAILED score"; exit 6; }
fi
{ echo "== $(date '+%F %T') L11 IL-151 superadiabatic penalty vs l21 stack seed 0 (DAY)"; $PY scripts/compare_headline.py ${B}_cal2021_smap_shufc8_headline.csv $H
  echo "physics rows (base | il151):"; grep -E "superadiabatic|shear_gt|sfc_jump" ${B}_cal2021_smap_shufc8_mc.csv | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" ${M}_s0_cal2021_smap_shufc8_mc.csv | sed 's/^/  il151 /'; } >> data/l3_verdicts.txt 2>&1
log done
