#!/bin/bash
# F-13: score p2f with ridge-forecast drivers (lead 6 months) in the 'unknown' set; compare unknown-driver skill with the analog draw. Waits for IL-92. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il92 done" data/ap_il92.log 2>/dev/null; do sleep 60; done
sleep 120
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --driver-mode ridge --driver-lead 6 > data/ap_f13_score.log 2>&1
{ echo "== F-13 ridge drivers (lead 6) vs analog drivers, p2f ERA5, 'unknown' set"; grep -E "skill_unknown|unknown" data/ap_f13_score.log | tail -8; } >> data/ap_s_verdicts.txt
echo "$(date '+%F %T') f13 done" >> data/ap_f13.log
