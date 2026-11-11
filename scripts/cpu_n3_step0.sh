#!/bin/bash
# N3 step 0 (New_Plan 10.4): does Mode F still gain from more real years? ENSF2 HRES-only recipe on data/modeF_ens, seed 0, trained on the last
# 1 / 2 / 3 / 4 years before the fixed 2020 validation year (--fit-years; 4 = the shipped split 2016-20). Range map 2021, test 2022 as always.
# Out: models/modeF_n3_fy{1..4}_eval.csv; with arg 1: seed 1, fit years 3 and 4 only -> models/modeF_n3_fy{3,4}_s1_eval.csv (the 3 -> 4 gain is near seed noise). Verdict: new_plan_kit/b5_n3_step0.py. Log: data/l3.log [N3S0].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N3S0] $*" >> data/l3.log; }
S=${1:-0}; NS="1 2 3 4"; SFX=""; [ "$S" != 0 ] && NS="3 4" && SFX="_s$S"
log "start seed $S"
for n in $NS; do
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed $S \
      --fit-years $n --out models/modeF_n3_fy$n$SFX.pt > data/n3_fy$n$SFX.log 2>&1 && log "fy$n$SFX done" || log "FAILED fy$n$SFX"
done
log done
