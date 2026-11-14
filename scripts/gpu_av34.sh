#!/bin/bash
# AV34 (New_Plan 13): AV17 (trust layer refit on the shipped l3_c4w stack, T and u 12-18 km at w = 1) with --min-gain 0.001 instead of 0.003. Rule: header of new_plan_kit/b45_av34_trust_mingain.py.
# 1. trust fit (IL-10 settings + two skips) on a model copy models/av34_l3_c4w.pt (same weights, so the trust file's hash check passes for the copies);
# 2. DAY scores seeds 0/1/2 with the shipped stack flags (as gpu_au1_fair.sh, minus --fair-baseline) plus --trust; 3. balloon (sonde) run seed 0 plus --trust;
# 4. verdict. Steps skip when their output exists. One scorer at a time; waits for >= 6 GB free RAM. Log: data/l3.log [AV34].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w PR=data/pilot/profiles80.zarr
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz TR=models/av34_l3_c4w.trust2021.npz
log() { echo "$(date '+%F %T') [AV34] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $PR $CAL $SM $LM $C.pt; do [ -e $f ] || { log "FAILED missing $f"; exit 1; }; done
for s in av34_l3_c4w av34_s0 av34_s1 av34_s2; do [ -f models/$s.pt ] || cp $C.pt models/$s.pt; done
log start
if [ ! -f $TR ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.trust --model models/av34_l3_c4w.pt --data $DA --calib $CAL --from-year 2021 --year 2023 --m 199 \
    --min-gain 0.001 --skip "RH:5-12 km" "RH:12-18 km" "T:12-18 km" "u:12-18 km" --no-second-map > data/av34_trust_fit.log 2>&1 \
    && log "trust fit done" || { log "FAILED trust fit"; exit 2; }
fi
score() {  # SEED
  [ -f models/av34_s$1_cal2021_trust_smap_shufc8_lmap_headline.csv ] && return 0; wait_free
  $PY -W ignore -u -m tempest.scoring.score --model models/av34_s$1.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $1 --calib $CAL --shuffle --template-cell 8 \
    --shear-map $SM --lapse-map $LM --trust $TR > data/av34_s$1.log 2>&1 && log "seed $1 scored" || log "FAILED seed $1"
}
score 0; score 1; score 2
if [ ! -f models/av34_s0_sonde_cal2021_trust_smap_headline.csv ]; then
  wait_free
  $PY -W ignore -u -m tempest.scoring.sonde --model models/av34_s0.pt --data $DA --profiles $PR --m 199 --first-test-year 2024 --last-test-year 2025 --calib $CAL --extras --shear-map $SM \
    --trust $TR > data/av34_sonde.log 2>&1 && log "sonde scored" || log "FAILED sonde"
fi
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b45_av34_trust_mingain.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
