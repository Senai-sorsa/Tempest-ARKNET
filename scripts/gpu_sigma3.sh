#!/bin/bash
# SIGMA stage 3 NEST (New_Plan 14.3): SIGMA stage 2's recipe (scripts/cpu_sigma2.sh) with --width 512 and --nest (lead day d uses the first k_d of 512
# hidden units, k_d from SIGMA's s table: small noise -> 512, largest -> 128; tempest/forecast/sigma.py nest_widths), on the GPU. One change against
# stage 2 (width + nest); depth 2 / coarse 4 / members 2 kept, so the comparison with stage 2 is clean (N6 also changed depth and heights).
# Phase 1: GPU fits (--fit-only, low RAM) beside AV29, each started only with >= 12 GB free. Phase 2: evaluations (20-24 GB peak) after [AV29] done,
# one at a time. Reference: the N5 binned models modeF_n5_bin{,_den}_s{0,1}; same rows. Verdict: new_plan_kit/b20_sigma_stage3.py.
# Launch: nohup bash scripts/gpu_sigma3.sh &  Log: data/l3.log [SIG3]; per-run logs data/sig3_<name>{,_eval}.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [SIG3] $*" >> data/l3.log; }
free_gb() { powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
R="--width 512 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --device cuda"
RUNS="0: 0:_den 1: 1:_den"
log "start"
for r in $RUNS; do
  S=${r%%:*}; tag=${r##*:}; rows=data/modeF_v2$([ -n "$tag" ] && echo _denver); name=nest${tag}_s$S
  [ -f models/modeF_n5_$name.pt ] && { log "$name fit exists, kept"; continue; }    # rerun after a stop: keep the fits already made
  until [ "$(free_gb)" -ge 12 ]; do sleep 30; done
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows $R --retrain --fit-only --seed $S --out models/modeF_n5_$name.pt > data/sig3_$name.log 2>&1 && log "$name fit" || { log "FAILED fit $name"; exit 1; }
done
log "fits done; evals wait for AV29 to finish"
until grep -qE "[0-9] \[AV29\] done$" data/l3.log; do sleep 60; done
for r in $RUNS; do
  S=${r%%:*}; tag=${r##*:}; rows=data/modeF_v2$([ -n "$tag" ] && echo _denver); name=nest${tag}_s$S
  until [ "$(free_gb)" -ge 15 ]; do sleep 60; done
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows $R --seed $S --out models/modeF_n5_$name.pt > data/sig3_${name}_eval.log 2>&1 && log "$name done" || log "FAILED $name"
done
log done
