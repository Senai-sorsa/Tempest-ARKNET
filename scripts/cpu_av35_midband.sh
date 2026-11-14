#!/bin/bash
# AV35 (New_Plan 13): AV16 map + damped 5-12 km band, judged on 2021-22 balloons. Rule: header of new_plan_kit/b49_av35_damped_midband.py. CPU, about 10 min. Log: data/l3.log [AV35].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [AV35] $*" >> data/l3.log; }
[ -f models/il103_balloon_shearmap.npz ] || { log "FAILED missing models/il103_balloon_shearmap.npz"; exit 1; }
log start
PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore -u new_plan_kit/b49_av35_damped_midband.py > data/av35_midband.log 2>&1 && log done || log FAILED
