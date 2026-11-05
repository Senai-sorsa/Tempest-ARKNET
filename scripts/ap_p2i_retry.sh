#!/bin/bash
# Autopilot IL-56 retry: p2i (step weight 1.0) failed with a CUDA/cuBLAS error right after p2h ended; rerun it alone when the GPU is free (after IL-83). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il83 done" data/ap_shuf.log 2>/dev/null; do sleep 60; done
rm -f models/generator_80_p2i.pt.part
VAR=p2i FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_shear_chain_p2i_retry.log 2>&1
B=models/generator_80_p2i; A=models/generator_80_p2f
{ echo "== p2i (ERA5) vs p2f"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
  echo "== p2i (balloons) vs p2f"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5
  echo "== p2i physics"; $PY -c "
import pandas as pd
t=pd.read_csv('${B}_physics.csv'); t=t[t.set.isin(['truth','calibrated'])]; print(t[['band','set','shear_p99','shear_p999']].round(2).to_string(index=False))"; } >> data/ap_shear_verdicts.txt 2>&1
echo "$(date '+%F %T') p2i retry done" >> data/ap_shear.log
