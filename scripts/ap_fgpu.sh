#!/bin/bash
# BLOCK 0 GPU retrains one after the other, each judged on headline (ERA5 + balloons) AND shape with the p2f seed spread as tolerance:
# F-15 p2fm8 (m = 8 for the last 1500 steps), F-19 p2frh (RH-in-loss), F-14 p2fint (driver interactions). Waits for F-29. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "f29 done" data/ap_f29.log 2>/dev/null; do sleep 60; done
sleep 60
for V in p2fm8 p2frh p2fint; do
  VAR=$V FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_fgpu_chain.log 2>&1
  A=models/generator_80_p2f; B=models/generator_80_$V
  { echo "== BLOCK0 $V vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
    echo "== BLOCK0 $V vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
  bash scripts/shape_verdict.sh $V
done
echo "$(date '+%F %T') fgpu done" >> data/ap_fgpu.log
