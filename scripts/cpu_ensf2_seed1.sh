#!/bin/bash
# L14 ENSF2 second training seed (CPU): HRES-only base and IFS-ensemble features, same rows (data/modeF_ens), --seed 1, same recipe as the F-V2 runs.
# Compare models/modeF_ensbase_s1_eval.csv with models/modeF_ens_s1_eval.csv (mean CRPS by lead). Log: data/l3.log [ENSF2S1].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [ENSF2S1] $*" >> data/l3.log; }
R="--rows-dir data/modeF_ens --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 1"
log start
$PY -W ignore -u scripts/il6_modeF.py $R --out models/modeF_ensbase_s1.pt > data/il14_ensbase_s1.log 2>&1 && log "base s1 done" || log "FAILED base s1"
$PY -W ignore -u scripts/il6_modeF.py $R --ens --out models/modeF_ens_s1.pt > data/il14_ens_s1.log 2>&1 && log "ens s1 done" || log "FAILED ens s1"
log done
