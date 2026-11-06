#!/bin/bash
# F-29 redo: p2f32 ran out of GPU memory (8M rows in float32). Train p2fs16 and p2fs32 on the same random 3M-row subset (float16 vs float32 storage) and compare. Waits for the F-11 part 2 run. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until [ -f data/ap_f11b.log2 ]; do sleep 60; done
sleep 60
for V in p2fs16 p2fs32; do VAR=$V FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_f29b_chain.log 2>&1; done
A=models/generator_80_p2fs16; B=models/generator_80_p2fs32
{ echo "== F-29 float32 vs float16 storage on the same 3M rows (ERA5)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== F-29 (balloons)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
bash scripts/shape_verdict.sh p2fs16; bash scripts/shape_verdict.sh p2fs32
echo "$(date '+%F %T') f29b done" >> data/ap_f29b.log
