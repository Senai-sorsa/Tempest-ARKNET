#!/bin/bash
# F-11 part 2: mode P with the post-2022 indicator; compare with the current mode P (hybrid 2.571) in the same evaluation. Waits for the F-20 chain so the GPU stays single-job. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "f20 done" data/ap_f20.log 2>/dev/null; do sleep 60; done
sleep 60
PYTHONPATH=. $PY -W ignore -u scripts/p4_modeP.py --out models/modeP_post.pt --post2022 --device cuda --retrain > data/ap_f11b.log 2>&1
{ echo "== F-11 part 2 mode P with post-2022 indicator (summary rows from p4_modeP; compare with models/modeP_eval.csv)"; grep -A12 "mean |cov99" data/ap_f11b.log | head -16; } >> data/ap_s_verdicts.txt
echo "$(date '+%F %T') f11b done" >> data/ap_f11b.log2
