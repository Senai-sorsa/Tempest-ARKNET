#!/bin/bash
# AU-6 fix (New_Plan 15.2): the shipped l3_c4wl seed 0 balloon (sonde) run, the gpu_au1_fair flags without --extras (--partial refuses it),
# once plain (flag off: score.csv must equal models/l3_c4wl_s0_sonde_cal2021_smap.score.csv) and once with --partial
# (keeps soundings with u, v, T to 5 km complete). The model is copied to models/au6_l3_c4wl_s0.pt so the shipped outputs stay.
# Then runs scripts/gpu_au5_freshpool.sh (AU-5 step 1, de-meaned pool) so only one GPU job runs at a time. Log: data/l3.log [AU6].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w PR=data/pilot/profiles80.zarr
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz M=models/au6_l3_c4wl_s0.pt
log() { echo "$(date '+%F %T') [AU6] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $CAL $SM models/l3_c4wl_s0.pt; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
cp models/l3_c4wl_s0.pt $M
log start
sonde() {  # TAG extra-args
  [ -f models/au6_l3_c4wl_s0_sonde_cal2021_smap$2_headline.csv ] && return 0
  wait_free
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $DA --profiles $PR --m 199 --first-test-year 2024 --last-test-year 2025 --calib $CAL --shear-map $SM ${3} \
    > data/au6_sonde_$1.log 2>&1 && log "sonde $1 scored" || log "FAILED sonde $1"
}
sonde plain "" ""
sonde partial _part --partial
cmp -s models/au6_l3_c4wl_s0_sonde_cal2021_smap.score.csv models/l3_c4wl_s0_sonde_cal2021_smap.score.csv && log "flag off: score.csv identical to the shipped run" || log "flag off: score.csv DIFFERS from the shipped run"
log done
bash scripts/gpu_au5_freshpool.sh
