#!/bin/bash
# L3-37: quasi-random generator noise at sampling (score.py --qmc: one scrambled Sobol set of m points per condition, a random
# shift per condition, normal quantile). Never tried at inference (F-15 antithetic noise was at training, discarded). No retrain.
# NM/TX headline (seed 0) vs models/g9_p2f_nmtx_cal2021_headline.csv; seed-to-seed spread of random vs qmc from model copies
# _s1/_s2 (the stem has no seed); Denver kept stack (L3-35 c8) with --qmc. Runs after L3-36 (scripts/ap_l3_nrh.sh), back to back.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
B=models/generator_80_p2f C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz
NX=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz G=models/g9_p2f_nmtx
log() { echo "$(date '+%F %T') [L3-37] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring' }).Count" | tr -d '\r'; }
until grep -q "\[L3-36\] done" data/l3.log; do sleep 120; done
sleep 90
while [ "$(busy)" != "0" ]; do sleep 60; done
log start
for s in 1 2; do [ -f ${G}_s$s.pt ] || cp $G.pt ${G}_s$s.pt; done
S="$PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --calib $C"
run() { local n=$1 l=$2; shift 2; $S "$@" > $l 2>&1 && log "$n scored" || log "FAILED $n"; }
run nmtx_qmc_s0 data/l3_qmc_nmtx_s0.log --model $G.pt --data $NX --qmc --seed 0
for s in 1 2; do
  run nmtx_rand_s$s data/l3_qmc_nmtx_rand_s$s.log --model ${G}_s$s.pt --data $NX --seed $s
  run nmtx_qmc_s$s data/l3_qmc_nmtx_s$s.log --model ${G}_s$s.pt --data $NX --qmc --seed $s
done
run den_stack_qmc data/l3_qmc_den.log --model models/l3_p2fden_fx.pt --data $DEN --qmc --trust models/l3_p2fden.trust2021.npz --shuffle --template-cell 8 --shear-map $SM
log done
