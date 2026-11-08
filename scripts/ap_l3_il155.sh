#!/bin/bash
# L17 / IL-155 + IL-113: an untouched confirmation window. The IL-76 model (models/l3_il76.pt: trained <= 2018, early stopping 2019-20, never saw 2021-25) is calibrated on 2021-22 only
# and scored on 2023 (untouched by any calibration or earlier accept/reject decision) and on 2024-25 (the development window used for 20+ decisions), DAY and NIGHT. A headline on 2023 that matches 2024-25 says the 2024-25 numbers are not much optimistic.
# Waits for no other loop-3 queue, no GPU/build job and >= 6 GB free RAM; every step skips when its output exists, retried once. Log: data/l3.log [IL155]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
M=models/l3_il155 C=models/l3_il155.calib2021.npz   # a COPY of l3_il76.pt: spread.py names its output after the model, so the il76 calibration file is not touched
log() { echo "$(date '+%F %T') [IL155] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!il155)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $A21 $DA $NI models/l3_il76.pt; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start; [ -f $M.pt ] || cp models/l3_il76.pt $M.pt
if [ ! -f $C ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2022 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_il155.log 2>&1 || { log "FAILED spread (see data/l3_calib_il155.log)"; exit 4; }
fi
score() {  # score TAG DATA FIRST LAST
  local S=${M}_$1.pt H=${M}_$1_cal2122_headline.csv
  cp $M.pt $S; [ -f $H ] && return 0
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $S --data $2 --m 199 --first-test-year $3 --last-test-year $4 --calib $C > data/l3_score_il155_$1.log 2>&1 && log "il155 $1 scored" || { log "FAILED score $1"; return 1; }
}
score d2023 $DA 2023 2023; score d2425 $DA 2024 2025; score n2023 $NI 2023 2023; score n2425 $NI 2024 2025
for t in d n; do
  [ -f ${M}_${t}2425_cal2122_headline.csv ] && [ -f ${M}_${t}2023_cal2122_headline.csv ] && { echo "== $(date '+%F %T') L17 IL-155 confirmation window: 2024-25 (base) vs untouched 2023 (new), il76 model, calibration 2021-22, $t"; $PY scripts/compare_headline.py ${M}_${t}2425_cal2122_headline.csv ${M}_${t}2023_cal2122_headline.csv; } >> data/l3_verdicts.txt 2>&1
done
log done
