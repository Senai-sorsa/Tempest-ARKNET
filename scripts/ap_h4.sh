#!/bin/bash
# Loop 2 H4: p2fmix = RH-in-loss weight 0.1 + last 1500 steps with m = 6; headline (ERA5 + balloons) and shape vs p2f. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
VAR=p2fmix FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_h4_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2fmix
{ echo "== LOOP2 H4 p2fmix vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== LOOP2 H4 p2fmix vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
bash scripts/shape_verdict.sh p2fmix
echo "$(date '+%F %T') h4 done" >> data/ap_h4.log
