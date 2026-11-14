#!/bin/bash
# AV20 (New_Plan 13): SIREN + climatology inputs. Rule: header of new_plan_kit/b55_av20_siren_clim.py.
# 1. overlays (scripts/av20_overlay.py on the l3x overlays) if missing; 2. train configs/generator_av20.toml on NM/TX (as scripts/ap_l3.sh run());
# 3. range calibration 2021-23; 4. NM/TX score 2024-25; 5. shape diag; 6. Denver fill-top zero-shot score with the NM/TX calibration (as ap_l3_fill.sh);
# 7. verdict. Steps skip when their output exists. One GPU job at a time. Log: data/l3.log [AV20].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd_av20.npz DEN=data/train/denver_full_fill_dpd_av20.npz CFG=configs/generator_av20.toml
M=models/av20.pt C=models/av20.calib2021.npz DM=models/av20_denfill.pt
log() { echo "$(date '+%F %T') [AV20] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest|diagnose' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
log start
[ -f $NT ] || PYTHONPATH=. $PY -W ignore scripts/av20_overlay.py data/train/pilot80_dpd_l3x.npz $NT >> data/av20_overlay.log 2>&1 || { log "FAILED nm/tx overlay"; exit 1; }
[ -f $DEN ] || PYTHONPATH=. $PY -W ignore scripts/av20_overlay.py data/train/denver_full_fill_dpd_l3x.npz $DEN >> data/av20_overlay.log 2>&1 || { log "FAILED denver overlay"; exit 1; }
if [ ! -f $M ]; then
  wait_free
  $PY -u -m tempest.generator.train --data $NT --out $M.part --max-year 2023 --min-year 1991 --config $CFG > data/av20_train.log 2>&1 && mv $M.part $M && log trained || { log "FAILED train"; exit 2; }
fi
if [ ! -f $C ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $NT --year 2023 --from-year 2021 --rows 60000 --m 199 > data/av20_calib.log 2>&1 && log calibrated || { log "FAILED spread"; exit 2; }
fi
if [ ! -f models/av20_cal2021_headline.csv ]; then
  wait_free
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $NT --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/av20_score.log 2>&1 && log "nm/tx scored" || { log "FAILED nm/tx score"; exit 2; }
fi
if [ ! -f models/av20_shape_diag.csv ]; then
  wait_free
  PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $NT --out models/av20_shape_diag > data/av20_shape.log 2>&1 && log "shape done" || { log "FAILED shape"; exit 2; }
fi
if [ ! -f models/av20_denfill_cal2021_headline.csv ]; then
  wait_free; cp $M $DM
  $PY -W ignore -u -m tempest.scoring.score --model $DM --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/av20_denfill.log 2>&1 && log "denver scored" || { log "FAILED denver score"; exit 2; }
fi
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b55_av20_siren_clim.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
