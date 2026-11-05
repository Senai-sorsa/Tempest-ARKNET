#!/bin/bash
# F-29: float32 vs float16 training-row storage (external review 1.1 / 1.2 / 3.1). Same config and seed as p2f; verdict on headline + shape. Waits for IL-94. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il94 done" data/ap_il94.log 2>/dev/null; do sleep 60; done
sleep 60
VAR=p2f32 FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f29_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2f32
{ echo "== F-29 p2f32 (float32 storage) vs p2f (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-29 p2f32 vs p2f (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
bash scripts/shape_verdict.sh p2f32
echo "$(date '+%F %T') f29 done" >> data/ap_f29.log
