#!/bin/bash
# IL-192 (CPU): mode F with IFS-ensemble features at Denver, paired with the HRES-only base on the SAME rows (data/modeF_ens_denver from `scripts/il14_ens_rows.py denver`).
# Recipe = the NM/TX ENSF2 pair: --rows-dir data/modeF_ens_denver --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 1 (CPU).
# Compare models/modeF_ensbase_den_s1_eval.csv with models/modeF_ens_den_s1_eval.csv (mean CRPS by lead, method 'network + PIT recal + range map + Schaake shuffle'). Log: data/l3.log [ENSDENS1].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [ENSDENS1] $*" >> data/l3.log; }
R="--rows-dir data/modeF_ens_denver --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 1"
log start
$PY -W ignore -u scripts/il6_modeF.py $R --out models/modeF_ensbase_den_s1.pt > data/il14_ensbase_den_s1.log 2>&1 && log "base done" || log "FAILED base"
$PY -W ignore -u scripts/il6_modeF.py $R --ens --out models/modeF_ens_den_s1.pt > data/il14_ens_den_s1.log 2>&1 && log "ens done" || log "FAILED ens"
log done
