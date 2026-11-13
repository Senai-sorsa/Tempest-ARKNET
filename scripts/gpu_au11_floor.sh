#!/bin/bash
# AU-11 step 0 (New_Plan 15.3): the shipped l3_c4wl seed 0 ERA5 score (gpu_au1_fair flags without --fair-baseline), run through
# scripts/au11_step0.py, which counts per column how often the batch width floor of the range map binds. Model copied to
# models/au11_l3_c4wl_s0.pt so the shipped outputs stay. Writes models/au11_step0.csv. Log: data/l3.log [AU11].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz M=models/au11_l3_c4wl_s0.pt
log() { echo "$(date '+%F %T') [AU11] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $CAL $SM $LM models/l3_c4wl_s0.pt; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
cp models/l3_c4wl_s0.pt $M
log start; wait_free
PYTHONPATH=. $PY -W ignore -u scripts/au11_step0.py --out models/au11_step0.csv -- --model $M --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 \
  --mc --seed 0 --calib $CAL --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/au11_step0.log 2>&1 \
  && { grep "^\[AU11\]" data/au11_step0.log >> data/l3.log; log done; } || log "FAILED (data/au11_step0.log)"
