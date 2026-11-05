#!/bin/bash
# Re-score E12 with the refitted trust layer (weights + second range map). Log: data/phase1b.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
P=data/pilot/profiles80.zarr; D=data/train/pilot80_smix.npz
M=models/generator_80_b0smix.pt; C=models/generator_80_b0smix.calib2021.npz; T=models/generator_80_b0smix.trust2021.npz
log() { echo "$(date '+%F %T') $*" >> data/phase1b.log; }
log start
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --trust $T --extras > data/p1b_era_trust.log 2>&1 || log "FAILED era"
log "era done"
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --trust $T --extras > data/p1b_sonde_trust.log 2>&1 || log "FAILED sonde"
log "phase1b done"
