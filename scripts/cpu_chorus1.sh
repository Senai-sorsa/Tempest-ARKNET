#!/bin/bash
# CHORUS stage 1 (New_Plan 14.4; no training): the shipped-recipe own-box mode F networks (models/modeF_n2_base{,_den}{,_s1}.pt, HRES-only ENSF2 rows)
# scored on 2022 twice on the SAME rows: as is (newest run) and with the closed-rule mix of the newest and the 36 h older run
# (data/chorus_<box>_mix from scripts/chorus_stage1_rows.py). The networks are copied (models/chorus_{new,mix}<tag><sfx>.pt), so no shipped file is rewritten.
# One evaluation at a time (14-17 GB RAM peak). Launch: nohup bash scripts/cpu_chorus1.sh &  Log: data/l3.log [CHORUS1]; per run data/chorus1_<name>.log.
# Verdict: new_plan_kit/b9_chorus_stage1.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [CHORUS1] $*" >> data/l3.log; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
log "start"
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in "modeF_ens::nmtx" "modeF_ens_denver:_den:denver"; do
    src=${box%%:*}; rest=${box#*:}; tag=${rest%%:*}; b=${rest##*:}
    for arm in new mix; do
      name=$arm$tag$sfx; out=models/chorus_$name.pt
      [ -f models/chorus_${name}_rows.npz ] && { log "$name exists, skipped"; continue; }
      cp -n models/modeF_n2_base$tag$sfx.pt $out
      rows=data/$src; [ $arm = mix ] && rows=data/chorus_${b}_mix
      while [ "$(powershell -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -lt 15 ]; do sleep 60; done
      $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows $SMALL --seed $S --out $out > data/chorus1_$name.log 2>&1 && log "$name done" || log "FAILED $name"
    done
  done
done
log done
