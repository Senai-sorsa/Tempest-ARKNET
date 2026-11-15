#!/bin/bash
# UR1 TAILCAL (New_Plan 17.1) inputs: re-score the EXISTING N5 binned, SIGMA stage 2 and NEST networks (no training) on 2022 and on 2021 with
# il6_modeF.py --save-members (members of the final method -> data/kit/ur_members/<arm><tag>_s<seed>_y<year>.npz) and --stem-suffix _mem
# (new output names, so no earlier eval / rows file is overwritten). Same flags as the runs that made the networks (cpu_n5_full.sh,
# cpu_sigma2.sh, gpu_sigma3.sh), without --retrain. 24 evaluations, one at a time (each peaks at 14-17 GB RAM; NEST evaluates on the GPU).
# The _mem rows files are also the reference rows of UR2 (b26_ur2_stack.py). Verdict: new_plan_kit/b25_ur1_tailcal.py.
# Launch: nohup bash scripts/cpu_ur1_members.sh &   Log: data/l3.log [UR1]; per run data/ur1_<name>.log. A rerun keeps finished files.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [UR1] $*" >> data/l3.log; }
free_gb() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*il6_modeF.py*' }).Count"; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads"
declare -A ARM=( [bin]="$SMALL" [sig]="$SMALL --sigma" [nest]="${SMALL/--width 128/--width 512} --sigma --nest --device cuda" )
mkdir -p data/kit/ur_members
log "start"
for arm in bin sig nest; do
  for S in 0 1; do
    for box in "modeF_v2:" "modeF_v2_denver:_den"; do
      rows=data/${box%%:*}; tag=${box##*:}; name=$arm${tag}_s$S; net=models/modeF_n5_$name.pt
      [ -f $net ] || { log "MISSING network $net, skipped"; continue; }
      for Y in 2022 2021; do
        out=data/kit/ur_members/${name}_y$Y.npz
        [ -f $out ] && { log "$name $Y exists, kept"; continue; }
        until [ "$(busy)" -le 1 ] && [ "$(free_gb)" -ge 15 ]; do sleep 60; done     # 1 = this runner's own check line is not a Mode F job; wait for other Mode F jobs
        yr=$([ $Y = 2021 ] && echo "--test-year 2021" || echo "")
        $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows ${ARM[$arm]} --seed $S --out $net $yr --stem-suffix _mem --save-members $out \
          > data/ur1_${name}_$Y.log 2>&1 && log "$name $Y done" || log "FAILED $name $Y"
      done
    done
  done
done
log done
