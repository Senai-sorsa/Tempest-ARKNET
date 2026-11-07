#!/bin/bash
# L3-40 Denver stack on all hours. L3-38/39 made l3_h_all24 the NM/TX base (day unchanged, night -0.0072 -> +0.0274), but
# the Denver stack (+0.0100: p2f + trust fitted on Denver 2021-23 + shear map + shuffle c8) is day only. Builds the Denver
# night hours (UTC 05-11) from the raw store (it already holds all 24 h, no download), then rebuilds the stack on all24
# (its own NM/TX shear map, trust fitted on Denver day + night 2021-23) and scores, all with --mc, seed 0:
#   DAY   all24 stack vs the +0.0100 p2f stack (models/l3_p2fden_fx_cal2021_trust_smap_shufc8_headline.csv)
#   NIGHT all24 stack vs the p2f stack extrapolating into the night
# Starts when no other loop-3 queue or GPU/build job runs. Every step skips when its output exists, so a relaunch resumes.
# Log: data/l3.log [L3-40]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
RAW=data/raw/era5_em_denver_full PN=data/pilot/profiles_denver_full_night.zarr
DEN=data/train/denver_full_fill_dpd.npz DNI=data/train/denver_full_fill_night_dpd.npz DA24=data/train/denver_full_fill_all24_dpd.npz
B=models/generator_80_p2f C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz T=models/l3_p2fden.trust2021.npz
A=models/l3_h_all24 CA=models/l3_h_all24.calib2021.npz SMA=models/l3_h_all24.shearmap2021_cell8.npz
MA=models/l3_a24den.pt TA=models/l3_a24den.trust2021.npz
VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [L3-40] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!denhours)|ap_l3\.sh' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 9 ]; do sleep 60; done; }

log "waiting for the loop-3 queue, GPU and builds"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 300; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
log start

# 1. Denver night store (UTC 05-11 = solar ~22-04 h at -105 deg), same as profiles_denver_full otherwise, no 2026
for try in 1 2; do
  [ -f $PN/COMPLETE ] && break
  wait_gpu; log "night store try $try"
  TEMPEST_REGION=configs/region_denver.toml CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.profiles.to_heights --raw $RAW \
    --cds data/raw/empty_cds --out $PN --hours 5-11 --last-year 2025 >> data/l3_denhours_heights.log 2>&1 && touch $PN/COMPLETE
done
[ -f $PN/COMPLETE ] || { log "FAILED night store twice"; exit 2; }

# 2. night build at the day file's density (4.0 M rows from 17 h -> 1.65 M from 7 h), fill-top as the day file; then day + night
for try in 1 2; do
  [ -f $DNI ] && break
  wait_gpu; log "night build try $try"
  TEMPEST_REGION=configs/region_denver.toml CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles $PN \
    --out $DNI.part --rows 1650000 --first-year 1991 --last-year 2025 --station-map models/station_map_denver_full.npz \
    --features base --rh-target dpd --fill-top --all-hours >> data/l3_denhours_build.log 2>&1 && mv $DNI.part $DNI
done
[ -f $DNI ] || { log "FAILED night build twice"; exit 3; }
[ -f $DA24 ] || { wait_gpu; $PY -u scripts/concat_npz.py $DA24.part $DEN $DNI >> data/l3_denhours_build.log 2>&1 && mv $DA24.part $DA24; } \
  || { log "FAILED concat"; exit 3; }

# 3. stack parts for all24: shear map on NM/TX all hours (as p2f's IL-96 map), trust on Denver day + night 2021-23
if [ ! -f $SMA ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.shear_map --model $A.pt --data data/train/pilot80_all24_dpd.npz --calib $CA --shuffle --full \
    --template-cell 8 --out $SMA > data/l3_denhours_smap.log 2>&1 && log "all24 shear map fitted" || { log "FAILED shear map"; exit 4; }
fi
cp $A.pt $MA
if [ ! -f $TA ]; then
  wait_gpu
  $PY -W ignore -u -m tempest.calibrate.trust --model $MA --data $DA24 --calib $CA --from-year 2021 --year 2023 --m 199 \
    > data/l3_denhours_trust.log 2>&1 && log "all24 trust fitted on Denver day + night" || { log "FAILED trust fit"; exit 4; }
fi

# 4. scores (headline files follow the model copy's name, so every run gets its own copy)
run() {  # run COPY_STEM SRC_MODEL DATA CALIB TRUST SHEARMAP
  local M=models/$1.pt H=models/$1_cal2021_trust_smap_shufc8_headline.csv
  cp $2 $M
  [ -f $H ] && return 0
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc \
    --calib $4 --trust $5 --shuffle --template-cell 8 --shear-map $6 > data/l3_denhours_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; return 1; }
}
verdict() { [ -f $1 ] && [ -f $2 ] && { echo "== $(date '+%F %T') L3-40 $3"; $PY scripts/compare_headline.py $1 $2; } >> $VLOG 2>&1; }
run l3_p2fden_night models/l3_p2fden_fx.pt $DNI $C $T $SM
run l3_a24den_day $MA $DEN $CA $TA $SMA
run l3_a24den_night $MA $DNI $CA $TA $SMA
verdict models/l3_p2fden_fx_cal2021_trust_smap_shufc8_headline.csv models/l3_a24den_day_cal2021_trust_smap_shufc8_headline.csv "DENVER all24 stack DAY vs p2f stack (+0.0100)"
verdict models/l3_p2fden_night_cal2021_trust_smap_shufc8_headline.csv models/l3_a24den_night_cal2021_trust_smap_shufc8_headline.csv "DENVER all24 stack NIGHT vs p2f stack extrapolating"
log done
