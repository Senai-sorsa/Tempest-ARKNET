#!/bin/bash
# New_Plan 25 GF4: CPU conditional calibration on top of the paired base's full stack (b). Needs models/s25/base_s0.* from
#   bash scripts/s25_arm.sh base 0 configs/s25/base.toml          (the shared paired baseline; this script never trains)
# Dumps calibrated samples for 2021-23 (fit) and 2024-25 (score) with scripts/s25_shape.py --dump, fits scripts/s25_gf4_condcal.py,
# then the judge (new_plan_kit/s25_judges.py gf4, rule in its docstring).
#   nohup bash scripts/cpu_s25_gf4.sh > /dev/null 2>&1 &         log: docs/results/logs/s25_gf4.log, verdict: docs/results/logs/kit_s25_gf4.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python D=models/s25 L=docs/results/logs/s25_gf4.log DA=data/train/pilot80_l21_day_dpd.npz T=base_s0
M=$D/$T.pt C=$D/$T.calib2021.npz SM=$D/${T}_smap_cell8.npz LM=$D/${T}_lmap_cell8.npz
for f in $M $C $SM $LM; do [ -f $f ] || { echo "$(date '+%F %T') missing $f (run the base arm first)" >> $L; exit 2; }; done
STACK="--shuffle --template-cell 8 --shear-map $SM --lapse-map $LM --device cpu --m 99 --rows 4000"
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
[ "$DRY" = "1" ] || while [ "$(ram_gb)" -lt 4 ]; do sleep 60; done
run() { [ -e "$1" ] && return 0; shift; if [ "$DRY" = "1" ]; then echo "$*"; return 0; fi; "$@" >> $L 2>&1 || { echo "FAILED $*" >> $L; exit 2; }; }
run $D/gf4_fit.npz env PYTHONPATH=. $PY -W ignore scripts/s25_shape.py $M $C $DA --out $D/gf4_fit_shape --first-year 2021 --last-year 2023 $STACK --dump $D/gf4_fit.npz
run $D/gf4_score.npz env PYTHONPATH=. $PY -W ignore scripts/s25_shape.py $M $C $DA --out $D/gf4_score_shape --first-year 2024 --last-year 2025 $STACK --dump $D/gf4_score.npz
run $D/gf4_result.csv env PYTHONPATH=. $PY -W ignore scripts/s25_gf4_condcal.py $D/gf4_fit.npz $D/gf4_score.npz --out $D/gf4_result.csv
[ "$DRY" = "1" ] && exit 0
env "PYTHONPATH=.;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py gf4 >> $L 2>&1
