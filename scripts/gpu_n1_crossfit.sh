#!/bin/bash
# N1 (New_Plan 10.4): cross-fitted generator members, seeds 0 and 100 (the p2f and p2f_s1 seeds). See scripts/n1_crossfit.py.
# Part 1 now (GPU training + range map; waits inside for 10 GB free RAM before each fold): models/generator_80_n1cf{,_s1}.pt + .calibcf.npz.
# Part 2 after "[N6F] done" (scoring holds 11-14 GB RAM and the GPU): ERA5 score and balloon score on 2024-25, as scripts/phase2_variant.sh
# without --joint (the joint band is not in the N1 rule). Verdict: new_plan_kit/b5_crossfit.py against p2f / p2f_s1.
# Launch: powershell Start-Process bash.exe scripts/gpu_n1_crossfit.sh (detached). Log: data/l3.log [N1]; per-step data/n1_*.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=4 PYTHONPATH=.
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
log() { echo "$(date '+%F %T') [N1] $*" >> data/l3.log; }
log "start"
for v in ":0" "_s1:100"; do
  tag=${v%%:*}; M=models/generator_80_n1cf$tag.pt
  [ -f ${M%.pt}.calibcf.npz ] || $PY -W ignore -u scripts/n1_crossfit.py --seed ${v##*:} --out $M >> data/n1_train$tag.log 2>&1 && log "trained$tag" || { log "FAILED train$tag"; exit 4; }
done
log "waiting for N6F"
until grep -qE "\[N6F\] done$" data/l3.log; do sleep 60; done
for tag in "" "_s1"; do
  M=models/generator_80_n1cf$tag.pt; C=${M%.pt}.calibcf.npz
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --stress > data/n1_score$tag.log 2>&1 && log "era5 scored$tag" || log "FAILED score$tag"
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/n1_sonde$tag.log 2>&1 && log "balloons scored$tag" || log "FAILED sonde$tag"
done
log done
