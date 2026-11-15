#!/bin/bash
# AV19 shape inputs (fix 2026-11-14): compare_shape needs scripts/diagnose.py output (metric/var/band/value/goal), not the scorer's _diag.csv.
# diagnose.py with the full stack (calib + shuffle cell 8 + shear map + lapse map), NM/TX 2024-25: p2f seeds 0/1/2 (seed spread = tolerance) and studt seed 0. Then the b46 verdict.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz P=models/generator_80_p2f S=models/av19_studt
log() { echo "$(date '+%F %T') [AV19] $*" >> data/l3.log; }
diag() {  # OUT MODEL CALIB SHEARMAP LAPSEMAP SEED
  [ -f $1.csv ] && return 0
  PYTHONPATH=. $PY -W ignore -u scripts/diagnose.py $2 $3 $D --seed $6 --shuffle --template-cell 8 --shear-map $4 --lapse-map $5 --out $1 > data/$(basename $1).log 2>&1 \
    && [ -f $1.csv ] && log "$(basename $1) done" || { log "FAILED $(basename $1)"; exit 2; }
}
log "shape diags start"
for s in 0 1 2; do diag models/av19_shape_p2f_s$s $P.pt $P.calib2021.npz $P.shearmap2021_cell8.npz $P.lapsemap2021.npz $s; done
diag models/av19_shape_studt_s0 $S.pt models/l3_studt.calib2021.npz $S.shearmap2021_cell8.npz $S.lapsemap2021.npz 0
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b46_av19_studt_stack.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
