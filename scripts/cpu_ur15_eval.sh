#!/bin/bash
# UR15 + UR13 (New_Plan 17.2): score existing forecast-mode networks on the 2023-24 rows of scripts/ur15_opendata.py (ECMWF open data; il6_modeF.py
# --test-file, no training; range map on 2021 as for the 2022 test). Needs data/ur15_<box>_od/2324.npz for both boxes (ur15_opendata.py fetch, then
# rows). The mixed rows of UR13 are made here (ur15_opendata.py mix; needs the fetch with --with-older). Families, each with its networks' flags:
#   AV24 / UR13   chorus_new<tag><sfx> (plain rows) vs av24_mix<tag><sfx> (mixed rows), seeds 0 / 1
#   AV29          modeF_n2ft500<tag>_s<S> (--no-place) vs modeF_n2own500<tag>_s<S>, seeds 0 / 1 / 2
#   SIGMA / NEST  modeF_n5_{bin,sig,nest}<tag>_s<S>, seeds 0 / 1 (leads 1 / 3 / 5 / 7 d and 9 d with the default steps)
#   UR2 kept      ur2_ftnest<tag>_s<S> if they exist (--no-place)
# One evaluation at a time (14-17 GB). Outputs: <stem>_tf2324_{eval.csv,rows.npz}. Verdict: new_plan_kit/b37_ur15_third_period.py.
# Launch: nohup bash scripts/cpu_ur15_eval.sh &   Log: data/l3.log [UR15]; per run data/ur15_<name>.log. A rerun keeps finished files.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [UR15] $*" >> data/l3.log; }
free_gb() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)'; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*il6_modeF.py*' }).Count"; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
FT="--width 128 --depth 2 --coarse 4 --steps 500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
NEST="--width 512 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows --all-leads --sigma --nest --device cuda"
ev() {   # name net rows testfile flags... ; skips a network that does not exist or a run already done
  name=$1; net=$2; rows=$3; tf=$4; shift 4
  [ -f $net ] || { log "no $net, skipped"; return; }
  [ -f ${net%.pt}_tf2324_rows.npz ] && { log "$name exists, kept"; return; }
  until [ "$(busy)" -le 1 ] && [ "$(free_gb)" -ge 15 ]; do sleep 60; done
  $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows "$@" --save-cell-rows --out $net --test-file $tf > data/ur15_$name.log 2>&1 && log "$name done" || log "FAILED $name"
}
log "start"
for b in nmtx denver; do
  [ -f data/ur15_${b}_od/2324.npz ] || { log "rows missing for $b (run scripts/ur15_opendata.py fetch $b, then rows $b)"; continue; }
  [ -f data/ur15_${b}_od_mix/2324.npz ] || $PY -W ignore -u scripts/ur15_opendata.py mix $b >> data/ur15_mix_$b.log 2>&1 || log "FAILED mix $b"
  tag=$([ $b = denver ] && echo _den || echo ""); dn=$([ $b = denver ] && echo _denver || echo "")
  TF=data/ur15_${b}_od/2324.npz; TFM=data/ur15_${b}_od_mix/2324.npz
  for S in 0 1; do
    sfx=$([ $S = 0 ] && echo "" || echo "_s1")
    ev chorus_new$tag$sfx models/chorus_new$tag$sfx.pt data/modeF_ens$dn $TF $SMALL --seed $S
    ev av24_mix$tag$sfx models/av24_mix$tag$sfx.pt data/chorus_${b}_mixall $TFM $SMALL --seed $S
  done
  for S in 0 1 2; do
    ev n2ft500$tag$S models/modeF_n2ft500${tag}_s$S.pt data/modeF_ens$dn $TF $FT --no-place --seed $S
    ev n2own500$tag$S models/modeF_n2own500${tag}_s$S.pt data/modeF_ens$dn $TF $FT --seed $S
  done
  for S in 0 1; do
    ev bin$tag$S models/modeF_n5_bin${tag}_s$S.pt data/modeF_v2$dn $TF ${SMALL} --all-leads --seed $S
    ev sig$tag$S models/modeF_n5_sig${tag}_s$S.pt data/modeF_v2$dn $TF ${SMALL} --all-leads --sigma --seed $S
    ev nest$tag$S models/modeF_n5_nest${tag}_s$S.pt data/modeF_v2$dn $TF $NEST --seed $S
  done
  for S in 0 1 2; do
    ev ftnest$tag$S models/ur2_ftnest${tag}_s$S.pt data/modeF_v2$dn $TF $NEST --no-place --seed $S
    ev nest2$tag$S models/modeF_n5_nest${tag}_s$S.pt data/modeF_v2$dn $TF $NEST --seed $S
  done
done
log done
