#!/bin/bash
# AV16 (New_Plan 13): IL-103 balloon shear map at 12-18 km only, judged on 2021-22 balloons. Rule: header of new_plan_kit/b48_av16_aloft_shearmap.py. CPU, about 1 h. Log: data/l3.log [AV16].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [AV16] $*" >> data/l3.log; }
[ -f models/il103_balloon_shearmap.npz ] || { log "FAILED missing models/il103_balloon_shearmap.npz"; exit 1; }
log start
PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore -u new_plan_kit/b48_av16_aloft_shearmap.py > data/av16_aloft.log 2>&1 && log done || log FAILED
