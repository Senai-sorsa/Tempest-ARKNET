#!/bin/bash
# Autopilot group S (AUTOPILOT.md): IL-13 median shift, IL-12 shear patches at 5-12 km, IL-11 seasonal factors for RH/surface, IL-10 trust refit with gain margin.
# Waits for the IL-8 chain, runs one GPU job at a time, skips finished outputs (relaunch resumes), writes verdicts to data/ap_s_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export OMP_NUM_THREADS=12
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
B=models/generator_80_p2f
log() { echo "$(date '+%F %T') $*" >> data/ap_s.log; }
until grep -q "phase2 il8 done\|\[il8\] FAILED" data/phase2.log; do sleep 60; done
SC="-W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C"
SO="-W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C"
verdict() {  # suffix label balloons(1/0)
  { echo "== $2 (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_headline.csv ${B}_cal2021$1_headline.csv | tail -5
    if [ "$3" = 1 ]; then echo "== $2 (balloons)"; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021$1_headline.csv | tail -5; fi; } >> data/ap_s_verdicts.txt 2>&1
}
# IL-13 shift
[ -f ${B}.shift2021.npz ] || $PY -W ignore -u -m tempest.calibrate.shift --model $M --data $D --calib $C > data/ap_il13_fit.log 2>&1 || { log "FAILED il13 fit"; }
[ -f ${B}_cal2021_shift_headline.csv ] || $PY $SC --shift ${B}.shift2021.npz > data/ap_il13_score.log 2>&1 || log "FAILED il13 score"
[ -f ${B}_sonde_cal2021_shift_headline.csv ] || $PY $SO --shift ${B}.shift2021.npz > data/ap_il13_sonde.log 2>&1 || log "FAILED il13 sonde"
verdict _shift IL-13 1; log "il13 done"
# IL-12 patches at 5-12 km only
[ -f ${B}.sheartail2021_b2.npz ] || $PY -W ignore -u -m tempest.calibrate.shear_tail --model $M --data $D --calib $C --p 0.05 --only-bands 2 --out ${B}.sheartail2021_b2.npz > data/ap_il12_fit.log 2>&1 || log "FAILED il12 fit"
rm -f ${B}_cal2021_stail_headline.csv ${B}_sonde_cal2021_stail_headline.csv   # earlier IL-5 outputs share the suffix
$PY $SC --shear-tail ${B}.sheartail2021_b2.npz > data/ap_il12_score.log 2>&1 || log "FAILED il12 score"
$PY $SO --shear-tail ${B}.sheartail2021_b2.npz > data/ap_il12_sonde.log 2>&1 || log "FAILED il12 sonde"
verdict _stail IL-12 1; log "il12 done"
# IL-11 seasonal factors for RH + surface only (ERA5 only: sonde has no month hook)
[ -f ${B}.seasonal2021_rhsfc.npz ] || $PY -W ignore -c "
import numpy as np
from tempest.calibrate import seasonal
t = dict(np.load('${B}.seasonal2021.npz'))
r = seasonal.restrict(t, {'RH', 'rh2m'})
np.savez('${B}.seasonal2021_rhsfc.npz', **r)" > data/ap_il11_make.log 2>&1 || log "FAILED il11 make"
rm -f ${B}_cal2021_seas_headline.csv
$PY $SC --seasonal ${B}.seasonal2021_rhsfc.npz > data/ap_il11_score.log 2>&1 || log "FAILED il11 score"
verdict _seas IL-11 0; log "il11 done"
# IL-10 trust refit: gain margin 0.3 %, RH 5-18 km left alone, no second range map
[ -f ${B}.trust2021.npz ] || $PY -W ignore -u -m tempest.calibrate.trust --model $M --data $D --calib $C --min-gain 0.003 --skip "RH:5-12 km" "RH:12-18 km" --no-second-map > data/ap_il10_fit.log 2>&1 || log "FAILED il10 fit"
$PY $SC --trust ${B}.trust2021.npz > data/ap_il10_score.log 2>&1 || log "FAILED il10 score"
$PY $SO --trust ${B}.trust2021.npz > data/ap_il10_sonde.log 2>&1 || log "FAILED il10 sonde"
verdict _trust IL-10 1; log "il10 done"
log "group S done"
