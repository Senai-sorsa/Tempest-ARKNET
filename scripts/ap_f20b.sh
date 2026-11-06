#!/bin/bash
# F-20 redo: the first p2fblend run trained on the ordinary dataset (the blended build wrote x.npz.part.npz and the rename missed it). The blended dataset is now in place; retrain and judge on balloons. Runs at the end of the GPU queue. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until [ -f data/ap_il97.log ] && grep -q "il97 done" data/ap_il97.log; do sleep 60; done
sleep 60
VAR=p2fblend FEAT=base DS=pilot80_dpdblend bash scripts/phase2_variant.sh >> data/ap_f20b_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2fblend
{ echo "== F-20 (redo, real blended data) p2fblend vs p2f (balloons: independent truth)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5
  echo "== F-20 (redo) ERA5-type targets of its own dataset (different truth, indicative)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
CUDA_VISIBLE_DEVICES=-1 PYTHONPATH=. $PY -W ignore scripts/f20_seam.py $B.pt $B.calib2021.npz data/train/pilot80_dpdblend.npz >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') f20b done" >> data/ap_f20b.log
