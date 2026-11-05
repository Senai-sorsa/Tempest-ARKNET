#!/bin/bash
# Phase 1 end test (PHASED_PLAN 0.3 steps 2-3): E12 scored plain, then with the trust layer; ERA5 and balloons.
# The plain runs rewrite E12's own score files, so those are copied to models/e12_backup_phase1/ first and compared after.
# Log: data/phase1.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
P=data/pilot/profiles80.zarr; D=data/train/pilot80_smix.npz
M=models/generator_80_b0smix.pt; C=models/generator_80_b0smix.calib2021.npz
T=models/generator_80_b0smix.trust2021.npz; J=models/generator_80_b0smix.joint2021.npz
log() { echo "$(date '+%F %T') $*" >> data/phase1.log; }
B=models/e12_backup_phase1
if [ ! -d $B ]; then
  mkdir -p $B
  cp models/generator_80_b0smix_cal2021* models/generator_80_b0smix_sonde_cal2021.* models/generator_80_b0smix_sonde_cal2021_* $B/ 2>/dev/null
  cp -r models/generator_80_b0smix_cal2021_report models/generator_80_b0smix_sonde_cal2021_report $B/ 2>/dev/null
  log "backed up E12 score files to $B"
fi
SC="-W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C"
SO="-W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C"
log "phase1 start"
$PY $SC --extras --stress --joint $J > data/p1_era_plain.log 2>&1 || log "FAILED era plain"
log "era plain done"
$PY $SC --trust $T --extras > data/p1_era_trust.log 2>&1 || log "FAILED era trust"
log "era trust done"
$PY $SO --extras > data/p1_sonde_plain.log 2>&1 || log "FAILED sonde plain"
log "sonde plain done"
$PY $SO --trust $T --extras > data/p1_sonde_trust.log 2>&1 || log "FAILED sonde trust"
log "phase1 done"
