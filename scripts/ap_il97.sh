#!/bin/bash
# IL-97: p2fpp = p2f + explicit ONI x QBO30 / QBO50 products as linear effects; headline + shape verdict. Runs at the end of the GPU queue. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until [ -f data/ap_f19b.log ] && grep -q "f19b done" data/ap_f19b.log; do sleep 60; done
sleep 60
VAR=p2fpp FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_il97_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2fpp
{ echo "== IL-97 p2fpp vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== IL-97 p2fpp vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
bash scripts/shape_verdict.sh p2fpp
echo "$(date '+%F %T') il97 done" >> data/ap_il97.log
