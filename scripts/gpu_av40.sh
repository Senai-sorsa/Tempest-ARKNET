#!/bin/bash
# AV40 (New_Plan 13): AV21 with the climatology mean only (p2f + anom_clim + anom_mean_only). Rule: header of new_plan_kit/b58_av40_anom_mean.py.
# Copy of scripts/gpu_av21.sh with the av40 names (the Denver calibration re-tag is built in from the start).
# 1. train configs/generator_av40.toml on NM/TX (as scripts/ap_l3.sh run()); 2. range calibration 2021-23; 3. NM/TX score 2024-25; 4. shape diag;
# 5. Denver: refit the climatology table on Denver rows <= 2020 (scripts/av21_table.py), fill-top zero-shot score with the NM/TX calibration (as ap_l3_fill.sh);
# 6. verdict. Steps skip when their output exists. Waits for any earlier GPU chain (AV18). One GPU job at a time. Log: data/l3.log [AV40].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz CFG=configs/generator_av40.toml
M=models/av40.pt C=models/av40.calib2021.npz DM=models/av40_denfill.pt DC=models/av40_denfill.calib2021.npz
log() { echo "$(date '+%F %T') [AV40] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest|diagnose|av20_overlay' }).Count" | tr -d '\r'; }
chain() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'gpu_av18' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
while [ "$(chain)" != "0" ]; do sleep 120; done
log start
if [ ! -f $M ]; then
  wait_free
  $PY -u -m tempest.generator.train --data $NT --out $M.part --max-year 2023 --min-year 1991 --config $CFG > data/av40_train.log 2>&1 && mv $M.part $M && log trained || { log "FAILED train"; exit 2; }
fi
if [ ! -f $C ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $NT --year 2023 --from-year 2021 --rows 60000 --m 199 > data/av40_calib.log 2>&1 && log calibrated || { log "FAILED spread"; exit 2; }
fi
if [ ! -f models/av40_cal2021_headline.csv ]; then
  wait_free
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $NT --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/av40_score.log 2>&1 && log "nm/tx scored" || { log "FAILED nm/tx score"; exit 2; }
fi
if [ ! -f models/av40_shape_diag.csv ]; then
  wait_free
  PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $NT --out models/av40_shape_diag > data/av40_shape.log 2>&1 && log "shape done" || { log "FAILED shape"; exit 2; }
fi
if [ ! -f models/av40_denfill_cal2021_headline.csv ]; then
  wait_free
  [ -f $DM ] || PYTHONPATH=. $PY -W ignore scripts/av21_table.py $M $DEN $DM > data/av40_table.log 2>&1 || { log "FAILED denver table"; exit 2; }
  # the NM/TX calibration unchanged, re-tagged with the swapped model's hash (spread.load refuses a hash mismatch; only the table buffers differ)
  [ -f $DC ] || PYTHONPATH=. $PY -c "import sys, numpy as np; from tempest.calibrate.spread import model_hash; c = dict(np.load(sys.argv[1])); c['model_sha'] = np.array(model_hash(sys.argv[2])); np.savez(sys.argv[3], **c)" $C $DM $DC || { log "FAILED denver calib tag"; exit 2; }
  $PY -W ignore -u -m tempest.scoring.score --model $DM --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --calib $DC --extras > data/av40_denfill.log 2>&1 && log "denver scored" || { log "FAILED denver score"; exit 2; }
fi
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b58_av40_anom_mean.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
