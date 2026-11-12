#!/bin/bash
# N5 full run, the 3 runs cpu_n5_full.sh did not finish (its shells stopped 2026-11-11 ~18:01): all_s1 (its .pt exists, so evaluation only),
# bin_den_s1, all_den_s1. Same options as scripts/cpu_n5_full.sh (see its header); ends with "[N5F] done" so the N2 control starts.
# Launch: nohup bash scripts/cpu_n5_rest.sh > /dev/null 2>&1 &     Verdict: new_plan_kit/b5_modeF_alllead.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N5F] $*" >> data/l3.log; }
R="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads"
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/n5f_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "restart (3 missing runs)"
S=1
run all_s$S --rows-dir data/modeF_v2 $R --fit-beyond --seed $S --out models/modeF_n5_all_s$S.pt
run bin_den_s$S --rows-dir data/modeF_v2_denver $R --seed $S --out models/modeF_n5_bin_den_s$S.pt
run all_den_s$S --rows-dir data/modeF_v2_denver $R --fit-beyond --seed $S --out models/modeF_n5_all_den_s$S.pt
log done
