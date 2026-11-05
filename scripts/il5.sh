#!/bin/bash
# IL-5: rare shear patches on the adopted p2f model. Waits for the IL-3 chain to finish. Log: data/il5.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz
P=${P:-0.05}
until grep -q "phase2 il3 done\|\[il3\] FAILED" data/phase2.log; do sleep 60; done
$PY -W ignore -u -m tempest.calibrate.shear_tail --model $M --data $D --calib $C --p $P > data/il5_fit.log 2>&1 || { echo FAILED fit >> data/il5.log; exit 1; }
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --shear-tail models/generator_80_p2f.sheartail2021.npz > data/il5_score.log 2>&1 || { echo FAILED score >> data/il5.log; exit 2; }
echo "il5 done" >> data/il5.log
