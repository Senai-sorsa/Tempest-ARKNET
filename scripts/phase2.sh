#!/bin/bash
# Phase 2: build the p2 dataset, train once with all flags on, then the 0.3 test block. Every stage skips if its output
# exists, so a relaunch resumes. Log: data/phase2.log. Never edit while running. Variant: VAR=name uses configs/generator_${VAR}.toml
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
V=${VAR:-p2}
P=data/pilot/profiles80.zarr; S=models/station_map_mix.npz; D=data/train/pilot80_p2.npz
M=models/generator_80_$V.pt; C=models/generator_80_$V.calib2021.npz; CFG=configs/generator_$V.toml
log() { echo "$(date '+%F %T') [$V] $*" >> data/phase2.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights' }).Count" | tr -d '\r'; }
while [ "$(busy)" != "0" ]; do sleep 60; done
log start
[ -f $D ] || $PY -W ignore -u -m tempest.generator.build_dataset --profiles $P --out $D --first-year 1980 --last-year 2026 --station-map $S --features p2 --rh-target dpd >> data/phase2_build.log 2>&1 || { log "FAILED build"; exit 3; }
[ -f $M ] || { $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --min-year 1991 --config $CFG > data/phase2_train_$V.log 2>&1 && mv $M.part $M; } || { log "FAILED train"; exit 4; }
log "trained"
[ -f $C ] || $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/phase2_$V.log 2>&1 || { log "FAILED spread"; exit 5; }
J=models/generator_80_$V.joint2021.npz
[ -f $J ] || $PY -W ignore -u -m tempest.calibrate.joint --model $M --data $D --calib $C >> data/phase2_$V.log 2>&1 || log "FAILED joint"
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --stress --joint $J > data/phase2_score_$V.log 2>&1 || { log "FAILED score"; exit 6; }
log "era5 scored"
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/phase2_sonde_$V.log 2>&1 || { log "FAILED sonde"; exit 7; }
log "balloons scored"
PYTHONPATH=. $PY -W ignore scripts/physics.py $M $C $D --out models/generator_80_${V}_physics.csv > data/phase2_physics_$V.log 2>&1 || log "FAILED physics"
log "phase2 $V done"
