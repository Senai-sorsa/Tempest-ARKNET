#!/bin/bash
# New_Plan 27.3 / 29 X2: members of the EXISTING ur2_ftnest networks (SIGMA + NEST + world start + 500; no training) on the 2023-24 rows of
# scripts/ur15_opendata.py, so a tail table fit on the 2021 + 2022 members (data/kit/ur_members/ftnest*_y2022*.npz) can be judged there.
# Same flags as cpu_ur15_eval.sh's ftnest runs, plus --save-members and --stem-suffix _mem (new names: <stem>_mem_tf2324_*; nothing overwritten).
# One evaluation at a time (14-17 GB RAM), waits for no other il6_modeF.py job and >= 15 GB free. A rerun keeps finished files.
# Launch: nohup bash scripts/cpu_x2_ftnest_members.sh &   Log: data/l3.log [X2]; per run data/x2_<name>.log.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [X2] $*" >> data/l3.log; }
free_gb() { awk '/MemFree/ {print int($2/1048576)}' /proc/meminfo; }
busy() { tasklist //FI "IMAGENAME eq python.exe" //FI "MEMUSAGE gt 2000000" //NH | grep -c "^python" ; }   # shortcut: any python > 2 GB counts as a Mode F eval (they use 14-17 GB)
NEST="--width 512 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --device cuda"
mkdir -p data/kit/ur_members
log "start"
for b in nmtx denver; do
  tag=$([ $b = denver ] && echo _den || echo ""); dn=$([ $b = denver ] && echo _denver || echo "")
  TF=data/ur15_${b}_od/2324.npz
  [ -f $TF ] || { log "rows missing for $b"; continue; }
  for S in 0 1; do
    name=ftnest${tag}_s$S; net=models/ur2_ftnest${tag}_s$S.pt; out=data/kit/ur_members/${name}_tf2324.npz
    [ -f $net ] || { log "no $net, skipped"; continue; }
    [ -f $out ] && { log "$name exists, kept"; continue; }
    until [ "$(busy)" -eq 0 ] && [ "$(free_gb)" -ge 15 ]; do sleep 60; done
    $PY -W ignore -u scripts/il6_modeF.py --rows-dir data/modeF_v2$dn $NEST --no-place --seed $S --out $net --test-file $TF \
      --save-cell-rows --stem-suffix _mem --save-members $out > data/x2_$name.log 2>&1 && log "$name done" || log "FAILED $name"
  done
done
log done
