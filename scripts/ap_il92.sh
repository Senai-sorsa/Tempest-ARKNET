#!/bin/bash
# IL-92: seed noise of the headline. Two retrains of p2f with other seeds (same data, same config), verdicts against p2f. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -qF "[p2fb] phase2 p2fb done" data/phase2.log; do sleep 30; done
for n in 1 2; do
  V=p2f_s$n
  VAR=$V FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_il92_chain.log 2>&1
  A=models/generator_80_p2f; B=models/generator_80_$V
  { echo "== IL-92 $V vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
    echo "== IL-92 $V vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
done
echo "$(date '+%F %T') il92 done" >> data/ap_il92.log
