#!/bin/bash
# E12: mixed-era balloon map (RH from 2022-23, T/u/v from 1991-2020); retrain B0, score 2024-25 balloons. Log: data/e12.log
# Compare data/e12_sonde.log with data/rescore_sonde_b0.log (ERA5 scores are not comparable: the targets change). Log: data/e12.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
P=data/pilot/profiles80.zarr; S=models/station_map_mix.npz; D=data/train/pilot80_smix.npz
M=models/generator_80_b0smix.pt; C=models/generator_80_b0smix.calib2021.npz
log() { echo "$(date '+%F %T') $*" >> data/e12.log; }
trains() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|scoring' }).Count" | tr -d '\r'; }
while [ "$(trains)" != "0" ]; do sleep 120; done
log "e12 start"
[ -f $D ] || $PY -W ignore -u -m tempest.generator.build_dataset --profiles $P --out $D --first-year 1980 --last-year 2026 --station-map $S >> data/e12.log 2>&1 || { log "FAILED build"; exit 3; }
[ -f $M ] || { $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --min-year 1991 > data/e12_train.log 2>&1 && mv $M.part $M; } || { log "FAILED train"; exit 4; }
[ -f $C ] || $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/e12.log 2>&1 || { log "FAILED spread"; exit 8; }
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C > data/e12_sonde.log 2>&1 || { log "FAILED sonde"; exit 7; }
log "e12 done"
