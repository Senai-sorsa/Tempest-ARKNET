#!/bin/bash
# UR2 stages 4 and 5 (New_Plan 17.1). Run after the stage 3 verdict (new_plan_kit/b26_ur2_stack.py --stage 3); BASE says which stage is kept:
#   BASE=nest  (stage 3 not kept)  each network starts fresh, as SIGMA stage 3 (NEST)
#   BASE=ft    (stage 3 kept)      each network = the stage 3 world network (models/ur2_wnest_s<S>.pt) + 500 box steps, --no-place
# Stage 4: the same recipe on the mixed rows of scripts/ur2_mix_rows.py (data/ur2_<box>_mixv2; built here if missing), compared with the
#          BASE networks on the plain rows (b26 --stage 4). Seeds 0 / 1 / 2, both boxes, 2022 and 2021, members saved.
# Stage 5: the ensemble spread scales s (il6_modeF.py --sigma-ens-scale; the ensemble is not a network input). Only the ensemble rows have the
#          feed (00Z, leads 1-7 d): data/modeF_ens{,_denver}, or the older-run mixed ensemble rows data/chorus_<box>_mixall (AV24) when MIX=1
#          (stage 4 kept). Two arms on the SAME rows: without (_e0) and with (_e1) the scale. b26 --stage 5.
# Usage: BASE=nest MIX=0 STAGES="4 5" nohup bash scripts/gpu_ur2_stage45.sh &   Log: data/l3.log [UR2S45]; per run data/ur2s45_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
BASE=${BASE:-nest}; MIX=${MIX:-0}; STAGES=${STAGES:-"4 5"}
log() { echo "$(date '+%F %T') [UR2S45] $*" >> data/l3.log; }
free_gb() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*il6_modeF.py*' }).Count"; }
wait_eval() { until [ "$(busy)" -le 1 ] && [ "$(free_gb)" -ge 15 ]; do sleep 60; done; }
NEST="--width 512 --depth 2 --coarse 4 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --device cuda"
M=data/kit/ur_members
mkdir -p $M
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/ur2s45_$name.log 2>&1 && log "$name done" || { log "FAILED $name"; return 1; }; }
train_and_score() {   # name rows seed extra... : fit (BASE recipe) then score 2022 + 2021 with members; skips what exists
  name=$1; rows=$2; S=$3; shift 3
  net=models/ur2_${name}.pt
  if [ "$BASE" = ft ]; then start="--no-place --init models/ur2_wnest_s$S.pt --steps 500"; place="--no-place"; else start="--steps 1500"; place=""; fi
  [ -f $net ] || { wait_eval; run ${name}_fit --rows-dir $rows $NEST $start --retrain --fit-only --seed $S "$@" --out $net || return 1; }
  [ -f $M/${name}_y2022.npz ] || { wait_eval; run ${name}_y2022 --rows-dir $rows $NEST --steps 1500 $place --seed $S "$@" --out $net --stem-suffix _mem --save-members $M/${name}_y2022.npz; }
  [ -f $M/${name}_y2021.npz ] || { wait_eval; run ${name}_y2021 --rows-dir $rows $NEST --steps 1500 $place --seed $S "$@" --out $net --test-year 2021 --stem-suffix _mem --save-members $M/${name}_y2021.npz; }
}
log "start BASE=$BASE MIX=$MIX STAGES=$STAGES"
for st in $STAGES; do
  for b in nmtx denver; do
    tag=$([ $b = denver ] && echo _den || echo ""); plain=data/modeF_v2$([ $b = denver ] && echo _denver)
    if [ $st = 4 ]; then
      [ -f data/ur2_${b}_mixv2/2022.npz ] || { $PY -W ignore -u scripts/ur2_mix_rows.py $b > data/ur2s45_rows_$b.log 2>&1 && log "rows $b done" || { log "FAILED rows $b"; continue; }; }
      for S in 0 1 2; do
        [ "$BASE" = ft ] || [ -f models/modeF_n5_nest${tag}_s$S.pt ] || { log "missing BASE network nest${tag}_s$S (run gpu_ur2_stage3.sh first)"; }
        train_and_score s4mix_${BASE}${tag}_s$S data/ur2_${b}_mixv2 $S
      done
    else
      ens=$([ "$MIX" = 1 ] && echo data/chorus_${b}_mixall || echo data/modeF_ens$([ $b = denver ] && echo _denver))
      for S in 0 1 2; do
        train_and_score s5_${BASE}_m${MIX}${tag}_s${S}_e0 $ens $S
        train_and_score s5_${BASE}_m${MIX}${tag}_s${S}_e1 $ens $S --sigma-ens-scale
      done
    fi
  done
done
log done
