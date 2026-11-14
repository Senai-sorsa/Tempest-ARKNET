#!/bin/bash
# New_Plan 13 AV30: SIGMA stage 3 NEST (scripts/gpu_sigma3.sh) plus Student-t noise (--noise-t-dims 8 --noise-t-nu 4). One change against NEST.
# Phase 1: GPU fits (--fit-only, >= 12 GB free). Phase 2: evaluations one at a time (20-24 GB peak, >= 15 GB free). Verdict: new_plan_kit/b21_av30_nest_t.py.
# Launch: nohup bash scripts/gpu_av30.sh &  Log: data/l3.log [AV30]; per-run logs data/av30_<name>{,_eval}.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV30] $*" >> data/l3.log; }
free_gb() { powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
R="--width 512 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --noise-t-dims 8 --noise-t-nu 4 --device cuda"
RUNS="0: 0:_den 1: 1:_den"
log "start"
for r in $RUNS; do
  S=${r%%:*}; tag=${r##*:}; rows=data/modeF_v2$([ -n "$tag" ] && echo _denver); name=nestt${tag}_s$S
  [ -f models/modeF_n5_$name.pt ] && { log "$name fit exists, kept"; continue; }    # rerun after a stop: keep the fits already made
  until [ "$(free_gb)" -ge 12 ]; do sleep 30; done
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows $R --retrain --fit-only --seed $S --out models/modeF_n5_$name.pt > data/av30_$name.log 2>&1 && log "$name fit" || { log "FAILED fit $name"; exit 1; }
done
for r in $RUNS; do
  S=${r%%:*}; tag=${r##*:}; rows=data/modeF_v2$([ -n "$tag" ] && echo _denver); name=nestt${tag}_s$S
  until [ "$(free_gb)" -ge 15 ]; do sleep 60; done
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows $R --seed $S --out models/modeF_n5_$name.pt > data/av30_${name}_eval.log 2>&1 && log "$name done" || log "FAILED $name"
done
log done
