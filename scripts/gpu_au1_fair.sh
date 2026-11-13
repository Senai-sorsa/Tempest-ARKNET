#!/bin/bash
# AU-1 step 5 (New_Plan 15.1): the shipped l3_c4w stack (+ lapse map, DAY data, the exact flags of the l3_c4wl headline runs in gpu_direct_l21_stack.sh)
# rescored with --fair-baseline at score seeds 0 and 1 (outputs: models/l3_c4wl_s{0,1}_cal2021_smap_shufc8_lmap_fair_*; the plain headlines stay as they are),
# then one balloon (sonde) run plain and one with --fair-baseline, same inputs. Steps skip when their headline exists. Waits for >= 6 GB free RAM and no other scorer.
# Log: data/l3.log [AU1].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w PR=data/pilot/profiles80.zarr
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
log() { echo "$(date '+%F %T') [AU1] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $CAL $SM $LM models/l3_c4wl_s0.pt models/l3_c4wl_s1.pt; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
log start
score() {  # STEM SEED
  [ -f models/$1_cal2021_smap_shufc8_lmap_fair_headline.csv ] && return 0; wait_free
  $PY -W ignore -u -m tempest.scoring.score --model models/$1.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $2 --calib $CAL --shuffle --template-cell 8 \
    --shear-map $SM --lapse-map $LM --fair-baseline > data/au1_$1_fair.log 2>&1 && log "$1 fair scored" || log "FAILED $1 fair"
}
score l3_c4wl_s0 0
score l3_c4wl_s1 1
sonde() {  # TAG extra-args
  wait_free
  $PY -W ignore -u -m tempest.scoring.sonde --model models/l3_c4wl_s0.pt --data $DA --profiles $PR --m 199 --first-test-year 2024 --last-test-year 2025 --calib $CAL --extras --shear-map $SM "${@:2}" \
    > data/au1_sonde_$1.log 2>&1 && log "sonde $1 scored" || log "FAILED sonde $1"
}
sonde plain
sonde fair --fair-baseline
log done
