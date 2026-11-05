#!/bin/bash
# Autopilot shear track, training variants (AUTOPILOT.md IL-54..IL-57): p2g = shear-tail weight 2, p2h = weight 4, p2i = step weight 1.0, p2j = tail quantile 0.8.
# Each runs the full phase2_variant.sh stages (train, calibrate, score ERA5, score balloons, physics) one after the other, then compares with p2f.
# Waits for the earlier chains. Log data/ap_shear.log, verdicts data/ap_shear_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
until grep -q "il28 done\|FAILED il28" data/ap_next2.log 2>/dev/null; do sleep 60; done
for V in p2g p2h p2i p2j; do
  VAR=$V FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/ap_shear_chain_$V.log 2>&1
  B=models/generator_80_$V; A=models/generator_80_p2f
  { echo "== $V (ERA5) vs p2f"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5
    echo "== $V (balloons) vs p2f"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5
    echo "== $V physics (calibrated rows, shear p50/p99/p99.9 by band; truth first)"; $PY -c "
import pandas as pd
for f in ('${A}_physics.csv','${B}_physics.csv'):
    t=pd.read_csv(f); t=t[t.set.isin(['truth','calibrated'])]
    print(f); print(t[['band','set','shear_p99','shear_p999']].round(2).to_string(index=False))
"; } >> data/ap_shear_verdicts.txt 2>&1
  echo "$(date '+%F %T') $V done" >> data/ap_shear.log
done
echo "$(date '+%F %T') shear training group done" >> data/ap_shear.log
