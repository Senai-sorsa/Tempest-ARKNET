#!/bin/bash
# ENSF2 third training seed (CPU, user 2026-11-11 "rerun the strong candidates"): same recipe and rows as cpu_ensf2_seed1.sh / cpu_ensf2_denver_s1.sh, --seed 2.
# Compare models/modeF_ensbase{,_den}_s2_eval.csv with models/modeF_ens{,_den}_s2_eval.csv (mean CRPS by lead). Log: data/l3.log [ENSF2S2].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [ENSF2S2] $*" >> data/l3.log; }
C="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 2"
log start
$PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens $C --out models/modeF_ensbase_s2.pt > data/il14_ensbase_s2.log 2>&1 && log "base s2 done" || log "FAILED base s2"
$PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens $C --ens --out models/modeF_ens_s2.pt > data/il14_ens_s2.log 2>&1 && log "ens s2 done" || log "FAILED ens s2"
$PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens_denver $C --out models/modeF_ensbase_den_s2.pt > data/il14_ensbase_den_s2.log 2>&1 && log "base den s2 done" || log "FAILED base den s2"
$PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens_denver $C --ens --out models/modeF_ens_den_s2.pt > data/il14_ens_den_s2.log 2>&1 && log "ens den s2 done" || log "FAILED ens den s2"
log done
