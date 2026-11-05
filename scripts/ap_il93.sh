#!/bin/bash
# IL-93: (1) shape diagnostics (new tie-aware tail metric) for p2f, its two extra seeds, p2fv, p2fb; (2) clean w-head: train <= 2018, early stop 2019-20, range map on 2021-23 with 6000 rows. Waits for IL-92 and F-13. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "f13 done" data/ap_f13.log 2>/dev/null; do sleep 60; done
sleep 60
for V in p2f p2f_s1 p2f_s2 p2fv p2fb; do bash scripts/shape_verdict.sh $V; done
D=data/train/pilot80_dpd.npz
[ -f models/whead_clean.pt ] || PYTHONPATH=. $PY -W ignore -u scripts/whead.py train --data $D --w data/train/pilot80_w.npz --out models/whead_clean.pt --max-year 2020 --val-years 2 > data/ap_il93_whead.log 2>&1
PYTHONPATH=. $PY -W ignore -u scripts/whead_calib.py --model models/generator_80_p2f.pt --calib models/generator_80_p2f.calib2021.npz --data $D --w data/train/pilot80_w.npz --head models/whead_clean.pt --fit-rows 6000 --rows 3000 >> data/ap_il93_whead.log 2>&1
{ echo "== IL-93 clean w head (train<=2018, early stop 2019-20, range map 2021-23, 6000 fit rows)"; tail -9 data/ap_il93_whead.log; } >> data/ap_s_verdicts.txt
echo "$(date '+%F %T') il93 done" >> data/ap_il93.log
