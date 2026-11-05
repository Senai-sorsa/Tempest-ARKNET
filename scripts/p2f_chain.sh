#!/bin/bash
# Queue P2-f (EMA alone on top of p2e) after the vertical-wind head finished. Log: data/phase2.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
until grep -q "whead done\|FAILED" data/whead.log 2>/dev/null; do sleep 60; done
{ cat configs/generator_p2e.toml; echo; echo "# ---- p2f: P2-e + EMA of the weights (2.5 alone)"; echo "ema_decay = 0.999"; } > configs/generator_p2f.toml
VAR=p2f FEAT=base DS=pilot80_dpd OMP_NUM_THREADS=12 bash scripts/phase2_variant.sh
