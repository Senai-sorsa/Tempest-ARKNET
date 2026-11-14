#!/bin/bash
# AV15 (New_Plan 13): shear target hybrid (c1 at 1-5 km, ratio 1.33 at 5-18 km), judged on fresh 2022 balloons. Rule: header of new_plan_kit/b50_av15_shear_hybrid.py. CPU, about 35 min, 8 GB RAM. Log: data/l3.log [AV15].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [AV15] $*" >> data/l3.log; }
log start
PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore -u new_plan_kit/b50_av15_shear_hybrid.py --device cpu > data/av15_hybrid.log 2>&1 && log done || log FAILED
