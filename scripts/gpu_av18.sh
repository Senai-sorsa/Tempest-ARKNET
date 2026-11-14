#!/bin/bash
# AV18 (New_Plan 13): IL-54 shear-tail weight 2.0 (p2g) on seeds 100 / 200 (configs/generator_p2g_s1 / _s2.toml), the full IL-54 pipeline
# (scripts/phase2_variant.sh, FEAT=base DS=pilot80_dpd; every stage skips when its output exists, so a relaunch resumes), then the verdict
# new_plan_kit/b57_av18_shear_tail_seeds.py (rule in its header). One GPU job at a time: phase2_variant waits while a train / calibrate / score runs.
# Log: data/l3.log [AV18]; stage log data/phase2.log [p2g_sN].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [AV18] $*" >> data/l3.log; }
log start
for V in p2g_s1 p2g_s2; do
  VAR=$V FEAT=base DS=pilot80_dpd bash scripts/phase2_variant.sh >> data/av18_$V.log 2>&1 || { log "FAILED $V (see data/phase2.log)"; exit 2; }
  [ -f models/generator_80_${V}_sonde_cal2021_headline.csv ] || { log "FAILED $V: no balloon headline"; exit 2; }
  log "$V done"
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b57_av18_shear_tail_seeds.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
