#!/bin/bash
# Loop 3 row L3-0a: Denver 1991-2025 data (ERA5 columns, heights, IGRA, station map, dataset). Every stage skips
# if its output exists, so a relaunch resumes. Log: data/l3.log. New files only; the 2016-2023 Denver files stay.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export TEMPEST_REGION=configs/region_denver.toml CUDA_VISIBLE_DEVICES=-1
R=data/raw/era5_em_denver_full; I=data/raw/igra_denver_full; P=data/pilot/profiles_denver_full.zarr
S=models/station_map_denver_full.npz; D=data/train/denver_full_dpd.npz
log() { echo "$(date '+%F %T') [L3-0a] $*" >> data/l3.log; }
log start
$PY -W ignore -u -m tempest.ingest.fetch_earthmover --out $R --first 1991 --last 2025-12-31 --workers 4 >> data/l3_fetch.log 2>&1 || { log "FAILED fetch"; exit 2; }
log fetched
$PY -W ignore -u -m tempest.profiles.to_heights --raw $R --cds data/raw/empty_cds --out $P >> data/l3_heights.log 2>&1 || { log "FAILED heights"; exit 3; }
log heights
[ -f $I/USM00072469-drvd.txt.zip ] || $PY -W ignore -u -m tempest.ingest.fetch_igra --out $I USM00072469 >> data/l3_igra.log 2>&1 || { log "FAILED igra"; exit 4; }
[ -f $S ] || $PY -W ignore -u -m tempest.calibrate.station --profiles $P --igra $I --out $S --first-year 1991 --last-year 2020 --check-to 2025 >> data/l3_station.log 2>&1 || { log "FAILED station"; exit 5; }
log "station map"
[ -f $D ] || { $PY -W ignore -u -m tempest.generator.build_dataset --profiles $P --out $D.part --rows 4000000 --first-year 1991 --last-year 2025 --station-map $S --features base --rh-target dpd >> data/l3_build.log 2>&1 && mv $D.part $D; } || { log "FAILED build"; exit 6; }
log "L3-0a done"
