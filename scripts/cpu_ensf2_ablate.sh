#!/bin/bash
# IL-195 (CPU): which part of the IFS-ensemble features carries the mode F gain? NM/TX rows data/modeF_ens, seed 1, same recipe as scripts/cpu_ensf2_seed1.sh.
# Runs --ens-cols spread (12 features) and --ens-cols mean (12 features); compare with models/modeF_ensbase_s1_eval.csv (none) and models/modeF_ens_s1_eval.csv (all 24).
# Compare mean CRPS by lead, method 'network + PIT recal + range map + Schaake shuffle'. Log: data/l3.log [ENSABL].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [ENSABL] $*" >> data/l3.log; }
R="--rows-dir data/modeF_ens --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 1 --ens"
log start
$PY -W ignore -u scripts/il6_modeF.py $R --ens-cols spread --out models/modeF_ens_spread_s1.pt > data/il14_ens_spread_s1.log 2>&1 && log "spread done" || log "FAILED spread"
$PY -W ignore -u scripts/il6_modeF.py $R --ens-cols mean --out models/modeF_ens_mean_s1.pt > data/il14_ens_mean_s1.log 2>&1 && log "mean done" || log "FAILED mean"
log done
