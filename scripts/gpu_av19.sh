#!/bin/bash
# AV19 (New_Plan 13): L3-26 Student-t model (models/l3_studt.pt, no retrain) inside the full stack. Rule: header of new_plan_kit/b46_av19_studt_stack.py.
# 1. studt shear map (stack recipe: --shuffle --full --template-cell 8) and lapse map (after the shear map) on data/train/pilot80_dpd.npz with studt's calibration;
# 2. NM/TX DAY score seed 0 with the full stack (base = existing g80lm_lmap_s0, p2f with its full stack, same data and flags);
# 3. Denver zero-shot (denver_full_fill_dpd) seed 0: p2f stack and studt stack; 4. verdict. Steps skip when their output exists.
# One scorer at a time; waits for >= 6 GB free RAM. Log: data/l3.log [AV19].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz
S=models/av19_studt P=models/generator_80_p2f
CAL=models/l3_studt.calib2021.npz SM=$S.shearmap2021_cell8.npz LM=$S.lapsemap2021.npz
PCAL=$P.calib2021.npz PSM=$P.shearmap2021_cell8.npz PLM=$P.lapsemap2021.npz
log() { echo "$(date '+%F %T') [AV19] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $D $DEN models/l3_studt.pt $CAL $P.pt $PCAL $PSM $PLM models/g80lm_lmap_s0_cal2021_smap_shufc8_lmap_headline.csv; do [ -e $f ] || { log "FAILED missing $f"; exit 1; }; done
[ -f $S.pt ] || cp models/l3_studt.pt $S.pt
for s in av19_s0 av19_studtden; do [ -f models/$s.pt ] || cp models/l3_studt.pt models/$s.pt; done
[ -f models/av19_p2fden.pt ] || cp $P.pt models/av19_p2fden.pt
log start
if [ ! -f $SM ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.shear_map --model $S.pt --data $D --calib $CAL --shuffle --full --template-cell 8 --out $SM > data/av19_smap.log 2>&1 && [ -f $SM ] \
    && log "shear map fitted" || { log "FAILED shear map"; exit 2; }
fi
if [ ! -f $LM ]; then
  wait_free
  $PY -W ignore -u -m tempest.calibrate.lapse_map --model $S.pt --data $D --calib $CAL --shear-map $SM --shuffle --template-cell 8 --out $LM > data/av19_lmap.log 2>&1 && [ -f $LM ] \
    && log "lapse map fitted" || { log "FAILED lapse map"; exit 3; }
fi
score() {  # STEM DATA CALIB SHEARMAP LAPSEMAP
  [ -f models/$1_cal2021_smap_shufc8_lmap_headline.csv ] && return 0; wait_free
  $PY -W ignore -u -m tempest.scoring.score --model models/$1.pt --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $3 --shuffle --template-cell 8 \
    --shear-map $4 --lapse-map $5 > data/$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
}
score av19_s0 $D $CAL $SM $LM
score av19_p2fden $DEN $PCAL $PSM $PLM
score av19_studtden $DEN $CAL $SM $LM
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/b46_av19_studt_stack.py >> data/l3.log 2>&1 && log done || log "FAILED verdict"
