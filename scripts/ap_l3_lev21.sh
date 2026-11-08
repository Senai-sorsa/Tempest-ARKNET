#!/bin/bash
# L3-44 21 levels (AUTOPILOT F-17 / 4.6 / IL-64): the CDS + ARCO boundary-layer fill (975-750 hPa, 8 levels) is complete
# for 1991-2025 (user, 2026-11-07). Rebuilds the NM/TX all-hours file with 21 pressure levels instead of 13, at the SAME
# row density as l3_h_all24 (1991-2025 share of its rows: day 8.95 M x 35/46, night 3.69 M x 35/46, --frac 0.633), trains
# the all24 recipe (p2f config) on it and scores on the NEW file (real 0-3 km levels = the better truth):
#   DAY / NIGHT  l3_h_l21 vs l3_h_all24, both scored on the 21-level file (same truth)
#   DENVER       l3_h_l21 vs l3_h_all24 zero-shot on the Denver fill file (Denver stays 13 levels: no fill there)
# Checked 18:50 Nov 7: fill grid matches era5_em80 exactly (grib and nc), no gaps; 21 vs 13 levels changes only < 6 km
# (u 0.4-1.0 m/s, T 0.4-1.5 K, RH 2-3 % at 0-2 km). Each 1991-2025 store (~54 + ~22 GB) is deleted after its build
# (to_heights rebuilds it in ~40 / 15 min). Starts when no other loop-3 queue or GPU/build job runs, >= 70 GB disk and
# >= 6 GB RAM are free. Every step skips when its output exists. Log: data/l3.log [L3-44]; verdicts: data/l3_verdicts.txt.
# Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
RAW=data/raw/era5_em80 CDS=data/raw/era5_cds
PD=data/pilot/profiles80_l21.zarr PN=data/pilot/profiles80_l21_night.zarr
DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz A21=data/train/pilot80_l21_all24_dpd.npz
DENF=data/train/denver_full_fill_dpd.npz
B=models/l3_h_all24 M=models/l3_h_l21
VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [L3-44] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!lev21)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
free_gb() { df -BG --output=avail /c | tail -1 | tr -dc '0-9'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
wait_room() { while [ "$(free_gb)" -lt "$1" ]; do log "waiting for disk: $(free_gb) GB free, need $1"; sleep 1800; done; }

log "waiting for the loop-3 queue, GPU, builds, 70 GB disk and 6 GB RAM"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 120; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
log start

# 1. store -> build -> delete store, day then night (CPU only; same station map / features / target as pilot80_all24)
part() {  # part STORE HOURS OUT ROWS ROOM_GB
  [ -f $3 ] && { [ -d $1 ] && rm -rf $1; return 0; }
  for try in 1 2; do
    [ -f $1/COMPLETE ] && break
    wait_gpu; wait_room $5; log "$1 to_heights try $try ($(cat $1/done.txt 2>/dev/null | wc -l) blocks done)"
    CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.profiles.to_heights --raw $RAW --cds $CDS --out $1 --hours $2 \
      --first-year 1991 --last-year 2025 >> data/l3_lev21_heights.log 2>&1 && touch $1/COMPLETE
  done
  [ -f $1/COMPLETE ] || { log "FAILED $1 to_heights twice"; return 1; }
  for try in 1 2; do
    [ -f $3 ] && break
    wait_gpu; wait_room 15; log "$3 build try $try"
    CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles $1 --out $3.part --rows $4 --first-year 1991 \
      --last-year 2025 --station-map models/station_map_mix.npz --features base --rh-target dpd --all-hours >> data/l3_lev21_build.log 2>&1 && mv $3.part $3
  done
  [ -f $3 ] || { log "FAILED $3 build twice"; return 1; }
  rm -rf $1; log "$3 built, store $1 deleted"
}
part $PD 12-23,0-4 $DA 6810000 70 || exit 2
part $PN 5-11 $NI 2810000 30 || exit 2
if [ ! -f $A21 ]; then
  wait_gpu
  $PY -u scripts/concat_npz.py $A21.part $DA $NI --frac 0.633 >> data/l3_lev21_build.log 2>&1 && mv $A21.part $A21 || { log "FAILED concat"; exit 3; }
fi

# 2. train + calibrate (the all24 recipe)
if [ ! -f $M.pt ]; then
  for try in 1 2; do
    wait_gpu; log "train try $try"
    $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_p2f.toml > data/l3_train_h_l21.log 2>&1 && mv $M.pt.part $M.pt && break
  done
  [ -f $M.pt ] || { log "FAILED train twice"; exit 4; }
fi
if [ ! -f $M.calib2021.npz ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_h_l21.log 2>&1 || { log "FAILED spread"; exit 4; }
fi

# 3. scores (copies named <stem>_TAG.pt so every headline gets its own name)
score() {  # score STEM TAG DATA
  local S=${1}_$2.pt H=${1}_$2_cal2021_headline.csv
  cp $1.pt $S; [ -f $H ] && return 0
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $S --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --calib $1.calib2021.npz --extras \
    > data/l3_score_h_$(basename $1)_$2.log 2>&1 && log "$(basename $S) scored" || { log "FAILED score $S"; return 1; }
}
verdict() { [ -f $1 ] && [ -f $2 ] && { echo "== $(date '+%F %T') L3-44 $3"; $PY scripts/compare_headline.py $1 $2; } >> $VLOG 2>&1; }
score $B l21day $DA; score $M l21day $DA
score $B l21night $NI; score $M l21night $NI
score $M denfill $DENF
verdict ${B}_l21day_cal2021_headline.csv ${M}_l21day_cal2021_headline.csv "21 levels DAY: l21 vs all24 (both on the 21-level truth)"
verdict ${B}_l21night_cal2021_headline.csv ${M}_l21night_cal2021_headline.csv "21 levels NIGHT: l21 vs all24 (both on the 21-level truth)"
verdict ${B}_denfill_cal2021_headline.csv ${M}_denfill_cal2021_headline.csv "21 levels DENVER fill zero-shot: l21 vs all24"
log done
