#!/bin/bash
# Queue P3-5 (1980 start, gmst inputs) after the EMA run p2f. Log: data/phase2.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
until grep -q "phase2 p2f done\|\[p2f\] FAILED" data/phase2.log 2>/dev/null; do sleep 60; done
VAR=p35 FEAT=p2 DS=pilot80_p2 MINY=1980 bash scripts/phase2_variant2.sh
