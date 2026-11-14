#!/bin/bash
# AV39 (New_Plan 13): SIREN + only the stratospheric climatology inputs (clim_T 12 / 15 / 18 km, clim_tropo). Rule: header of new_plan_kit/b59_av39_siren_strat.py.
# Copy of scripts/gpu_av20.sh: same overlay files (data/train/*_av20.npz, built by AV20), config configs/generator_av39.toml; waits for the AV40 chain.
# 1. overlays (scripts/av20_overlay.py on the l3x overlays) if missing; 2. train configs/generator_av39.toml on NM/TX (as scripts/ap_l3.sh run());
# 3. range calibration 2021-23; 4. NM/TX score 2024-25; 5. shape diag; 6. Denver fill-top zero-shot score with the NM/TX calibration (as ap_l3_fill.sh);
# 7. verdict. Steps skip when their output exists. One GPU job at a time. Log: data/l3.log [AV39].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd_av20.npz DEN=data/train/denver_full_fill_dpd_av20.npz CFG=configs/generator_av39.toml
M=models/av39.pt C=models/av39.calib2021.npz DM=models/av39_denfill.pt
log() { echo "$(date '+%F %T') [AV39] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest|diagnose' }).Count" | tr -d '\r'; }
chain() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'bash\.exe.? scripts/gpu_av40\.sh' }).Count" | tr -d '\r'; }   # the runner itself, not a shell whose text names it
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
while [ "$(chain)" != "0" ]; do sleep 120; done
log start
[ -f $NT ] || PYTHONPATH=. $PY -W ignore scripts/av20_overlay.py data/train/pilot80_dpd_l3x.npz $NT >> data/av39_overlay.log 2>&1 || { log "FAILED nm/tx overlay"; exit 1; }
[ -f $DEN ] || PYTHONPATH=. $PY -W ignore scripts/av20_overlay.py data/train/denver_full_fill_dpd_l3x.npz $DEN >> data/av39_overlay.log 2>&1 || { log "FAILED denver overlay"; exit 1; }
if [ ! -f $M ]; then
  wait_free
  $PY -u -m tempest.generator.train --data $NT --out $M.part --max-year 2023 --min-year 1991 --config $CFG > data/av39_train.log 2>&1 && mv $M.part $M && log trained || { log "FAILED train"; exit 2; }
fi
if [ ! -f $C ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $NT --year 2023 --from-year 2021 --rows 60000 --m 199 > data/av39_calib.log 2>&1 && log calibrated || { log "FAILED spread"; exit 2; }
fi
if [ ! -f models/av39_cal2021_headline.csv ]; then
  wait_free
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $NT --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/av39_score.log 2>&1 && log "nm/tx scored" || { log "FAILED nm/tx score"; exit 2; }
fi
if [ ! -f models/av39_shape_diag.csv ]; then
  wait_free
  PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $NT --out models/av39_shape_diag > data/av39_shape.log 2>&1 && log "shape done" || { log "FAILED shape"; exit 2; }
fi
if [ ! -f models/av39_denfill_cal2021_headline.csv ]; then
  wait_free; cp $M $DM
  $PY -W ignore -u -m tempest.scoring.score --model $DM --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/av39_denfill.log 2>&1 && log "denver scored" || { log "FAILED denver score"; exit 2; }
fi
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b59_av39_siren_strat.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
