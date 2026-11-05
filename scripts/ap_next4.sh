#!/bin/bash
# Autopilot IL-60: shear tail by layer and season for p2f without and with the shear map. Waits for the p2i retry. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
export OMP_NUM_THREADS=12 PYTHONPATH=.
until grep -q "p2i retry done" data/ap_shear.log 2>/dev/null; do sleep 60; done
B=models/generator_80_p2f
{ echo "== IL-60 99.9th ratio sample/truth by layer group and season, p2f"; .venv/Scripts/python -W ignore scripts/shear_by_layer.py $B.pt $B.calib2021.npz data/train/pilot80_dpd.npz
  echo "== with the shear map"; .venv/Scripts/python -W ignore scripts/shear_by_layer.py $B.pt $B.calib2021.npz data/train/pilot80_dpd.npz --shear-map $B.shearmap2021.npz; } > data/ap_il60.log 2>&1
echo "$(date '+%F %T') il60 done" >> data/ap_next4.log
