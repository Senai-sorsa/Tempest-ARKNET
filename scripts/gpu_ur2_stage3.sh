#!/bin/bash
# UR2 stage 3 (New_Plan 17.1): world start for SIGMA + NEST. Needs scripts/cpu_ur1_members.sh first (its _mem rows of NEST seeds 0 / 1 are the
# reference rows; missing ones are made here too). All new files: models/ur2_*; members in data/kit/ur_members/.
#   1. NEST seed 2 (both boxes): GPU fit as gpu_sigma3.sh, then scored on 2022 and 2021 (_mem stems + members), so the rule has 3 seeds.
#   2. World network per seed 0 / 1 / 2: SIGMA target with tables from the 645k world rows (il6_modeF.py --sigma --fit-rows-dir, UR2 stage 3
#      code), NEST widths from the world tables, --no-place (the world model has no place input, as N2 / N6), 3000 steps, --fit-only.
#   3. Step 0 (report only): the world network as it is, scored on each box's 2022 rows with the box tables (stem suffix _nm / _den).
#   4. Fine-tune: world start + 500 box steps (--init, --retrain, --no-place), scored on 2022 and 2021 (+ members) -> models/ur2_ftnest<tag>_s<S>.
#   5. Control (information): own NEST + 500 steps (--init own NEST) -> models/ur2_own500nest<tag>_s<S>, scored on 2022 and 2021.
# One Mode F evaluation at a time (waits for 15 GB free and no other il6_modeF job); fits wait for 12 GB. Verdict: new_plan_kit/b26_ur2_stack.py --stage 3.
# Launch: nohup bash scripts/gpu_ur2_stage3.sh &   Log: data/l3.log [UR2S3]; per run data/ur2s3_<name>.log. A rerun keeps finished files.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [UR2S3] $*" >> data/l3.log; }
free_gb() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*il6_modeF.py*' }).Count"; }
wait_eval() { until [ "$(busy)" -le 1 ] && [ "$(free_gb)" -ge 15 ]; do sleep 60; done; }
wait_fit() { until [ "$(free_gb)" -ge 12 ]; do sleep 30; done; }
NEST="--width 512 --depth 2 --coarse 4 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --device cuda"
M=data/kit/ur_members
mkdir -p $M
run() { name=$1; shift; $PY -W ignore -u scripts/il6_modeF.py "$@" > data/ur2s3_$name.log 2>&1 && log "$name done" || { log "FAILED $name"; return 1; }; }
both_years() {   # name net rows extra... : score an existing network on 2022 and 2021 with members (skips what exists)
  name=$1; net=$2; rows=$3; shift 3
  stem=${net%.pt}
  [ -f ${stem}_mem_rows.npz ] && [ -f $M/${name}_y2022.npz ] || { wait_eval; run ${name}_y2022 --rows-dir $rows $NEST --steps 1500 "$@" --out $net --stem-suffix _mem --save-members $M/${name}_y2022.npz; }
  [ -f ${stem}_mem_t2021_rows.npz ] && [ -f $M/${name}_y2021.npz ] || { wait_eval; run ${name}_y2021 --rows-dir $rows $NEST --steps 1500 "$@" --out $net --test-year 2021 --stem-suffix _mem --save-members $M/${name}_y2021.npz; }
}
log "start"
for S in 0 1 2; do
  # 1. own NEST (seed 2 is new; seeds 0 / 1 exist and are only scored if cpu_ur1_members.sh has not done it)
  for box in "modeF_v2:" "modeF_v2_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}; net=models/modeF_n5_nest${tag}_s$S.pt
    [ -f $net ] || { wait_fit; run nest${tag}_s${S}_fit --rows-dir $rows $NEST --steps 1500 --retrain --fit-only --seed $S --out $net || continue; }
    both_years nest${tag}_s$S $net $rows --seed $S
  done
  # 2. world network
  W=models/ur2_wnest_s$S.pt
  [ -f $W ] || { wait_fit; run wnest_s${S}_fit --rows-dir data/modeF_v2 --fit-rows-dir data/modeF_world --no-place $NEST --steps 3000 --retrain --fit-only --seed $S --out $W || continue; }
  for box in "modeF_v2:_nm" "modeF_v2_denver:_den"; do
    rows=data/${box%%:*}; sfx=${box##*:}; tag=${sfx/_nm/}
    # 3. step 0: world as it is (box tables), 2022 only
    [ -f models/ur2_wnest_s${S}${sfx}_rows.npz ] || { wait_eval; run wnest${sfx}_s${S}_asis --rows-dir $rows --no-place $NEST --steps 3000 --seed $S --out $W --stem-suffix $sfx; }
    # 4. world start + 500 box steps
    F=models/ur2_ftnest${tag}_s$S.pt
    [ -f $F ] || { wait_eval; run ftnest${tag}_s${S}_fit --rows-dir $rows --no-place --init $W --retrain $NEST --steps 500 --fit-only --seed $S --out $F || continue; }
    both_years ftnest${tag}_s$S $F $rows --no-place --seed $S
    # 5. control: own NEST + 500 steps (information)
    C=models/ur2_own500nest${tag}_s$S.pt
    [ -f $C ] || { wait_eval; run own500nest${tag}_s${S}_fit --rows-dir $rows --init models/modeF_n5_nest${tag}_s$S.pt --retrain $NEST --steps 500 --fit-only --seed $S --out $C || continue; }
    both_years own500nest${tag}_s$S $C $rows --seed $S
  done
done
log done
