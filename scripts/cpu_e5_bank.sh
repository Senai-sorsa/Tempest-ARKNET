#!/bin/bash
# E5 (New_Plan 16.4): the measured-profile bank as a third bar in the Earth-GRAM kit (tool, gaussfull, bank), report only, no rule. CPU, about 30 min. Log: data/l3.log [E5].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
log() { echo "$(date '+%F %T') [E5] $*" >> data/l3.log; }
log start
PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_gram_compare.py --standin --bank > data/e5_bank.log 2>&1 && log done || log FAILED
