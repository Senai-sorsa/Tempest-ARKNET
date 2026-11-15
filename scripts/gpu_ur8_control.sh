#!/bin/bash
# UR8 (New_Plan 17.2): the control for N1. Same recipe as gpu_n1_crossfit.sh, but every member holds out the SAME fold (scripts/n1_crossfit.py
# --same-fold 0: 2008-09 + 2016-17), so the members see the same number of years as the cross-fitted ones, including 2021-23, without cross-fitting.
# Seeds 0 and 100 (as N1). Then the ERA5 and balloon scores on 2024-25 with the same flags as N1. New files: models/generator_80_n1sf{,_s1}.*
# GPU training waits inside for 10 GB free; scoring holds 11-14 GB and the GPU: it waits for no other scoring job.
# Verdict: new_plan_kit/b31_ur8_control.py. Launch: nohup bash scripts/gpu_ur8_control.sh &   Log: data/l3.log [UR8]; per step data/ur8_*.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=4 PYTHONPATH=.
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
log() { echo "$(date '+%F %T') [UR8] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*tempest.scoring*' -or \$_.CommandLine -like '*il6_modeF.py*' -or \$_.CommandLine -like '*generator.train*' }).Count"; }
log "start"
for v in ":0" "_s1:100"; do
  tag=${v%%:*}; M=models/generator_80_n1sf$tag.pt
  for try in 1 2 3; do   # finished folds are kept, so a retry after a GPU fault repeats one member only
    [ -f ${M%.pt}.calibcf.npz ] || $PY -W ignore -u scripts/n1_crossfit.py --seed ${v##*:} --same-fold 0 --out $M >> data/ur8_train$tag.log 2>&1 && break
    log "train$tag try $try failed"
  done
  [ -f ${M%.pt}.calibcf.npz ] && log "trained$tag" || { log "FAILED train$tag"; exit 4; }
done
for tag in "" "_s1"; do
  M=models/generator_80_n1sf$tag.pt; C=${M%.pt}.calibcf.npz
  until [ "$(busy)" -le 1 ]; do sleep 60; done
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --stress > data/ur8_score$tag.log 2>&1 && log "era5 scored$tag" || log "FAILED score$tag"
  until [ "$(busy)" -le 1 ]; do sleep 60; done
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/ur8_sonde$tag.log 2>&1 && log "balloons scored$tag" || log "FAILED sonde$tag"
done
log done
