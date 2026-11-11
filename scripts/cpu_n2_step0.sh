#!/bin/bash
# N2 step 0 box checks (New_Plan 10.4): ENSF2 HRES-only recipe, seed 0, per box: base (as shipped), --levels13 (input only at the world store's
# 13 pressure levels), --no-place (lat / lon 0). Same-run base because seed noise is about 1 %. Out: models/modeF_n2_{base,l13,nop}{,_den}_eval.csv.
# Verdict: new_plan_kit/b5_n2_step0.py. Log: data/l3.log [N2S0].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [N2S0] $*" >> data/l3.log; }
log start
for box in "modeF_ens:" "modeF_ens_denver:_den"; do
  rows=data/${box%%:*}; tag=${box##*:}
  for arm in "base:" "l13:--levels13" "nop:--no-place"; do
    name=${arm%%:*}; opt=${arm#*:}
    $PY -W ignore -u scripts/il6_modeF.py --rows-dir $rows --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --seed 0 $opt \
        --out models/modeF_n2_$name$tag.pt > data/n2_$name$tag.log 2>&1 && log "$name$tag done" || log "FAILED $name$tag"
  done
done
log done
