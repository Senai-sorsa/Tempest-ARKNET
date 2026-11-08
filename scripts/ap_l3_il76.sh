#!/bin/bash
# L12-adjacent validity item L17 / IL-76: calibration and early-stopping windows no longer overlap. p2f trained on <= 2018 with early stopping on 2019-2020 (configs/generator_il76.toml, --max-year 2020), calibrated on 2021-23 as before, scored day and night on the 21-level truth with --extras and compared with models/l3_h_l21. NOTE the base model sees less training data (<= 2018 instead of <= 2023): judge coverage and PIT, not skill alone.
# calibrated the same way, scored on the DAY and NIGHT 21-level truth with --extras, and compared with the existing l3_h_l21 headlines (models/l3_h_l21_l21day_cal2021_headline.csv and ..._l21night_...).
# Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM; every step skips when its output exists and is retried once. Log: data/l3.log [IL76]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
M=models/l3_il76 B=models/l3_h_l21
log() { echo "$(date '+%F %T') [IL76] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!il76)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $A21 $DA $NI $B.pt configs/generator_il76.toml; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
log "waiting for the loop-3 queue, GPU and builds"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
if [ ! -f $M.pt ]; then
  for try in 1 2; do
    wait_gpu; log "train try $try"
    $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2020 --min-year 1991 --config configs/generator_il76.toml > data/l3_train_il76.log 2>&1 && mv $M.pt.part $M.pt && break
  done
  [ -f $M.pt ] || { log "FAILED train twice"; exit 4; }
fi
if [ ! -f $M.calib2021.npz ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_il76.log 2>&1 || { log "FAILED spread"; exit 4; }
fi
score() {  # score TAG DATA
  local S=${M}_$1.pt H=${M}_$1_cal2021_headline.csv
  cp $M.pt $S; [ -f $H ] && return 0
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $S --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --calib $M.calib2021.npz --extras > data/l3_score_il76_$1.log 2>&1 && log "il76 $1 scored" || { log "FAILED score $1"; return 1; }
}
score l21day $DA; score l21night $NI
for t in l21day l21night; do
  [ -f ${B}_${t}_cal2021_headline.csv ] && [ -f ${M}_${t}_cal2021_headline.csv ] && { echo "== $(date '+%F %T') L17 IL-76 split windows vs l3_h_l21 $t"; $PY scripts/compare_headline.py ${B}_${t}_cal2021_headline.csv ${M}_${t}_cal2021_headline.csv; echo "wind rows (base | il76):"; head -40 ${B}_${t}_cal2021_extras_wind.csv | sed 's/^/  base /'; head -40 ${M}_${t}_cal2021_extras_wind.csv | sed 's/^/  il76 /'; } >> data/l3_verdicts.txt 2>&1
done
log done
