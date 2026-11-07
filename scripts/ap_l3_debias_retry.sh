#!/bin/bash
# L3-34 retry: the first fit (ap_l3_debias.sh) used m = 8 against an m = 199 calibration and failed. debias.py now takes m
# from the calibration. Starts within 2 s of "[L3-34] done" (L3-35 finished) so it is on the GPU before the data-needs
# runner's first busy check (that runner waits on any 'scoring' process); fit + both scores run back to back, no gap.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz B=models/generator_80_p2f
C=$B.calib2021.npz MD=models/l3_p2fden.pt T=models/l3_p2fden.trust2021.npz DB=models/l3_p2fden.debias2021.npz
log() { echo "$(date '+%F %T') [L3-34] $*" >> data/l3.log; }
until grep -q "\[L3-34\] done" data/l3.log; do sleep 2; done
log "retry start (m from calib)"
S="$PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --model $MD --data $DEN --calib $C --debias $DB"
if $PY -W ignore -u -m tempest.scoring.debias --model $MD --calib $C --data $DEN --from-year 2021 --year 2023 > data/l3_debias_fit.log 2>&1; then
  log "debias fitted ($(tail -1 data/l3_debias_fit.log))"
  $S > data/l3_debias_den.log 2>&1 && log "den_debias scored" || log "FAILED den_debias"
  $S --trust $T > data/l3_debias_den_trust.log 2>&1 && log "den_debias_trust scored" || log "FAILED den_debias_trust"
else
  log "FAILED debias fit again ($(tail -1 data/l3_debias_fit.log))"
fi
log "retry done"
