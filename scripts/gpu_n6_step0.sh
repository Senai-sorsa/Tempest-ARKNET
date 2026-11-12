#!/bin/bash
# N6 step 0 (New_Plan 10.4): full-size Mode F (width 512, depth 4, 4 members, all 44 heights = --coarse 1) fitted on the world rows
# (data/modeF_world, 645k rows, no lat / lon) on the GPU. Rule set in the plan BEFORE this run: validation CRPS at step 2750 not above step 250,
# else stop N6. Fit only (--fit-only: no evaluation, so it can run beside the CPU Mode F chain); the 300-step box fine-tunes and their
# evaluations come after [N2B] done (one Mode F evaluation at a time, 14-17 GB).
# Launch: powershell Start-Process bash.exe scripts/gpu_n6_step0.sh (detached). Log: data/l3.log [N6S0]; training log data/n6_world_s0.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=4 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N6S0] $*" >> data/l3.log; }
log "start"
$PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_ens --fit-rows-dir data/modeF_world --no-place --width 512 --depth 4 --coarse 1 --members 4 \
  --steps 3000 --lr 3e-4 --wd 1e-2 --seed 0 --device cuda --fit-only --out models/modeF_n6w_s0.pt > data/n6_world_s0.log 2>&1 && log "world_s0 done" || log "FAILED world_s0"
log done
