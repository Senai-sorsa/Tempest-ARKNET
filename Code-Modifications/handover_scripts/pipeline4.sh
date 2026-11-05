#!/bin/bash
# Full-data pipeline (v4, mixed-era balloon map, honest split: train <=2020, val+calib 2021-23, test 2024-25, + range calibration): wait for all CDS months -> profiles_bl.zarr -> station map -> pilot_bl.npz (balloon-corrected) -> train -> score (ERA5 + balloons).
# Every stage skips if its output exists, so rerunning after a fix resumes. Log: data/pipeline.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') $*" >> data/pipeline.log; }
fetch_alive() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'fetch_cds' }).Count" | tr -d '\r'; }
gpu_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '\r '; }

log "pipeline start"
while :; do
  n=$(ls data/raw/era5_cds/*.grib 2>/dev/null | wc -l)
  [ "$n" -ge 420 ] && break
  if [ "$(fetch_alive)" = "0" ]; then
    log "CDS downloader not running ($n/420 months): restarting (ledger prevents duplicate requests)"
    $PY -W ignore -u -m tempest.ingest.fetch_cds >> data/cds.log 2>&1 &
  fi
  sleep 600
done
log "all 420 CDS months present"

for try in 1 2 3; do  # resumes from done.txt after a crash
  n_done=$(cat data/pilot/profiles_bl.zarr/done.txt 2>/dev/null | wc -l)
  [ "$n_done" -ge 36 ] && break
  log "to_heights try $try ($n_done/36 blocks done)"
  $PY -W ignore -u -m tempest.profiles.to_heights --out data/pilot/profiles_bl.zarr >> data/pipeline.log 2>&1
done
[ "$(cat data/pilot/profiles_bl.zarr/done.txt 2>/dev/null | wc -l)" -ge 36 ] || { log "FAILED: to_heights"; exit 2; }

if [ ! -f models/station_map_bl.npz ]; then
  log "station correction (balloons vs the new store)"
  # E12 (PLAN): T/u/v from the 1991-2020 fit, RH from 2022-23 (balloon RH sensor/processing shift in 2022)
  $PY -W ignore -u -m tempest.calibrate.station --profiles data/pilot/profiles_bl.zarr --out models/station_map_bl_2020.npz >> data/pipeline.log 2>&1 \
    && $PY -W ignore -u -m tempest.calibrate.station --profiles data/pilot/profiles_bl.zarr --out models/station_map_bl_2223.npz --first-year 2022 --last-year 2023 >> data/pipeline.log 2>&1 \
    && PYTHONPATH=. $PY -W ignore -u Code-Modifications/handover_scripts/mixmap.py models/station_map_bl_2020.npz models/station_map_bl_2223.npz models/station_map_bl.npz >> data/pipeline.log 2>&1 \
    || { log "FAILED: station"; exit 6; }
fi

if [ ! -f data/train/pilot_bl.npz ]; then
  log "build_dataset"
  $PY -W ignore -u -m tempest.generator.build_dataset --profiles data/pilot/profiles_bl.zarr --out data/train/pilot_bl.npz \
    --station-map models/station_map_bl.npz >> data/pipeline.log 2>&1 \
    || { log "FAILED: build_dataset"; exit 3; }
fi

while [ "$(gpu_used)" -gt 2000 ]; do log "GPU busy ($(gpu_used) MiB used), waiting"; sleep 600; done

if [ ! -f models/generator_pilot.pt ]; then
  log "train"
  $PY -u -m tempest.generator.train --data data/train/pilot_bl.npz --out models/generator_pilot.part.pt --max-year 2023 >> data/pipeline.log 2>&1 \
    && mv models/generator_pilot.part.pt models/generator_pilot.pt || { log "FAILED: train"; exit 4; }
fi
C=models/generator_pilot.calib2021.npz
if [ ! -f $C ]; then
  log "range calibration (2021-23, 60k rows)"
  $PY -W ignore -u -m tempest.calibrate.spread --model models/generator_pilot.pt --data data/train/pilot_bl.npz --year 2023     --from-year 2021 --rows 60000 --m 199 >> data/pipeline.log 2>&1 || { log "FAILED: spread"; exit 8; }
fi
log "score (2024-25, calibrated)"
$PY -W ignore -u -m tempest.scoring.score --model models/generator_pilot.pt --data data/train/pilot_bl.npz --m 199   --first-test-year 2024 --last-test-year 2025 --calib $C >> data/pipeline.log 2>&1 || { log "FAILED: score"; exit 5; }
log "score against balloons (2024-25, calibrated)"
$PY -W ignore -u -m tempest.scoring.sonde --model models/generator_pilot.pt --data data/train/pilot_bl.npz   --profiles data/pilot/profiles_bl.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C >> data/pipeline.log 2>&1 || { log "FAILED: sonde"; exit 7; }
log "pipeline done"
