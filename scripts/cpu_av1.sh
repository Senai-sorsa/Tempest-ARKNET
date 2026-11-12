#!/bin/bash
# AV1 (New_Plan 13.1) confirmation year: score the existing small own-box models (models/modeF_n2_base*) and the N6 big fine-tuned models
# (models/modeF_n6ft*) on 2021 (range map fit on 2022; no network saw 2021 in its fit or step choice). No training (il6_modeF.py --test-year 2021
# refuses to train). Outputs <stem>_t2021_eval.csv / _rows.npz beside the 2022 ones. One evaluation at a time (14-17 GB RAM peak).
# Launch: powershell Start-Process bash.exe scripts/cpu_av1.sh (detached). Log: data/l3.log [AV1]; per-run data/av1_<name>.log.
# Verdict: new_plan_kit/b8_av1_lead_split.py.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV1] $*" >> data/l3.log; }
SMALL="--width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2 --save-rows"
BIG="--no-place --width 512 --depth 4 --coarse 1 --members 4 --lr 3e-4 --wd 1e-2 --steps 300 --save-rows --device cuda"
run() { name=$1; shift; [ -f "$1" ] && { log "$name exists, skipped"; return; }; shift
        $PY -W ignore -u scripts/il6_modeF.py --test-year 2021 "$@" > data/av1_$name.log 2>&1 && log "$name done" || log "FAILED $name"; }
log "start"
for S in 0 1; do
  sfx=$([ $S = 0 ] && echo "" || echo "_s1")
  for box in "modeF_ens:" "modeF_ens_denver:_den"; do
    rows=data/${box%%:*}; tag=${box##*:}
    run base$tag$sfx models/modeF_n2_base$tag${sfx}_t2021_rows.npz --rows-dir $rows $SMALL --seed $S --out models/modeF_n2_base$tag$sfx.pt
    run big$tag$sfx models/modeF_n6ft${tag}_s${S}_t2021_rows.npz --rows-dir $rows $BIG --seed $S --out models/modeF_n6ft${tag}_s$S.pt
  done
done
log done
