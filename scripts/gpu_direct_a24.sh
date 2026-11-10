#!/bin/bash
# A24 (2026-11-10, user: "it should be able to cover the entire day" for ALL our data): the shipped tool models are day-only (solar 06-21: generator_80_c4w on pilot80_dpd, Denver
# l3_blocal_c4w on denver_full_dpd), although all-hours data and an all-hours NM/TX stack exist (L3-38..45: all hours cost nothing by day, night skill -0.007 -> +0.027).
# NM/TX: the all-hours C4w stack (models/l3_c4w + calib + own shear map + shuffle c8 + lapse map) vs the shipped stack (generator_80_c4w, same post-processing) on the same DAY rows,
#        on the 13-level day file (pilot80_dpd, the shipped model's own truth) and the 21-level day file; seeds 0 and 1. (Night: l3_c4wl_night exists; the day model has no night skill.)
# Denver: C4w trained on the all-hours Denver file (denver_full_fill_all24_dpd, 1991-2023) on training seeds 0 and 100, calibration 2021-23 on the same file; scored DAY on denver_full_dpd
#        paired with the installed day model (l3_blocal_c4w / _s1, same settings as their headlines) and NIGHT on denver_full_fill_night_dpd against the installed day model extrapolating.
# Waits for the gap test run ([TESTS] done) and >= 6 GB free RAM before each GPU step (one GPU job, B27). Log: data/l3.log [A24]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [A24] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
until grep -q '\[TESTS\] done' data/l3.log; do sleep 60; done
log start
# ---- NM/TX: shipped day stack vs all-hours stack, same rows
SH=models/generator_80_c4w NA=models/l3_c4w
nm() {  # nm STEM SOURCE DATA SEED
  local P=models/$1.pt; [ -f $P ] || cp $2.pt $P
  [ -f models/$1_cal2021_smap_shufc8_lmap_headline.csv ] && return 0; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model $P --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $4 --calib $2.calib2021.npz --shuffle --template-cell 8 \
    --shear-map $2.shearmap2021_cell8.npz --lapse-map $2.lapsemap2021.npz > data/l3_a24_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
}
nmv() { local A=models/$1_cal2021_smap_shufc8_lmap_headline.csv B=models/$2_cal2021_smap_shufc8_lmap_headline.csv
  [ -f $A ] && [ -f $B ] && { echo "== $(date '+%F %T') A24 NM/TX $3"; $PY scripts/compare_headline.py $A $B; } >> data/l3_verdicts.txt 2>&1; }
for s in 0 1; do
  nm a24_ship13_s$s $SH data/train/pilot80_dpd.npz $s; nm a24_all13_s$s $NA data/train/pilot80_dpd.npz $s
  nmv a24_ship13_s$s a24_all13_s$s "shipped day stack vs all-hours stack, DAY 13-level truth (pilot80_dpd), seed $s"
  nm a24_ship21_s$s $SH data/train/pilot80_l21_day_dpd.npz $s; nm a24_all21_s$s $NA data/train/pilot80_l21_day_dpd.npz $s
  nmv a24_ship21_s$s a24_all21_s$s "shipped day stack vs all-hours stack, DAY 21-level truth (pilot80_l21_day), seed $s"
done
nm a24_shipnight $SH data/train/pilot80_l21_night_dpd.npz 0; nm a24_allnight $NA data/train/pilot80_l21_night_dpd.npz 0
nmv a24_shipnight a24_allnight "shipped day stack (extrapolating) vs all-hours stack, NIGHT (pilot80_l21_night), seed 0"
log "nmtx done"
# ---- Denver: all-hours C4w
A=data/train/denver_full_fill_all24_dpd.npz DD=data/train/denver_full_dpd.npz DN=data/train/denver_full_fill_night_dpd.npz
for spec in "a24den_c4w configs/generator_c4w.toml l3_blocal_c4w" "a24den_c4w_s1 configs/generator_c4w_s1.toml l3_blocal_c4w_s1"; do
  set -- $spec; M=models/$1.pt C=models/$1.calib2021.npz
  [ -f $M ] || { wait_ram; log "$1 train"; $PY -u -m tempest.generator.train --data $A --out $M.part --max-year 2023 --min-year 1991 --config $2 > data/l3_train_$1.log 2>&1 && mv $M.part $M || { log "FAILED $1 train"; continue; }; }
  [ -f $C ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $A --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$1.log 2>&1 || { log "FAILED $1 spread"; continue; }; }
  [ -f models/$1_cal2021_headline.csv ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $M --data $DD --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/l3_score_$1.log 2>&1 && log "$1 day scored" || log "FAILED $1 day score"; }
  { echo "== $(date '+%F %T') A24 Denver all-hours C4w vs installed day model, DAY ($3 vs $1)"; $PY scripts/compare_headline.py models/$3_cal2021_headline.csv models/$1_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
done
# night: the installed day model extrapolating vs the all-hours model (training seed 0)
for spec in "a24den_dayn l3_blocal_c4w" "a24den_alln a24den_c4w"; do
  set -- $spec; P=models/$1.pt; [ -f $P ] || cp models/$2.pt $P
  [ -f models/$1_cal2021_headline.csv ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $DN --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/$2.calib2021.npz --extras > data/l3_score_$1.log 2>&1 && log "$1 night scored" || log "FAILED $1 night score"; }
done
{ echo "== $(date '+%F %T') A24 Denver NIGHT: installed day model (extrapolating) vs all-hours C4w"; $PY scripts/compare_headline.py models/a24den_dayn_cal2021_headline.csv models/a24den_alln_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
log done
