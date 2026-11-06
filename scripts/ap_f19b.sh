#!/bin/bash
# F-19 redo: the first p2frh run produced NaN from the first evaluation (unguarded saturation-vapour-pressure ratio); fixed with clamps. Runs after the whole queue. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until [ -f data/ap_f29b.log ] && grep -q "f29b done" data/ap_f29b.log; do sleep 60; done
sleep 60
rm -f models/generator_80_p2frh.pt.part
VAR=p2frh FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f19b_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2frh
{ echo "== F-19 (redo) p2frh vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-19 (redo) p2frh vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
bash scripts/shape_verdict.sh p2frh
echo "$(date '+%F %T') f19b done" >> data/ap_f19b.log
