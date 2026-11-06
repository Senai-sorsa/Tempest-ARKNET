#!/bin/bash
# Loop 2 H1b headline check: stack A + damped PIT + RH-profile seasonal above 1 km, ERA5 CRPS skill vs stack A. CPU only. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=. CUDA_VISIBLE_DEVICES=-1
B=models/generator_80_p2f
$PY -W ignore -u -m tempest.scoring.score --model $B.pt --data data/train/pilot80_dpd.npz --m 199 --first-test-year 2024 --last-test-year 2025 --calib $B.calib2021.npz --shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz --pit-recal $B.pitrecal2021.npz --pit-damp 0.5 --seasonal $B.seasonal2021_rhprof1km.npz > data/ap_h1c_score.log 2>&1
echo "$(date '+%F %T') h1c done" >> data/ap_h1c.log
