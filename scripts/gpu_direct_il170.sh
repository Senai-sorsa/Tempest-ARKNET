#!/bin/bash
# IL-170 (2026-11-10): Denver post-processing. The Denver tool models serve the calibrated network only (no shuffle templates, shear map or lapse map), while on NM/TX each of the three
# helped (lapse map: superadiabatic 33.8 -> 23.6 %, T better in every band). For the Denver DAY model (l3_blocal_c4w, denver_full_dpd) and the Denver ALL-HOURS model (a24den_c4w,
# denver_full_fill_all24_dpd): fit the shear map and the lapse map on their own stack (calibration + shuffle with 2-degree templates, as NM/TX), score the stack (--mc) paired with the plain
# calibrated model, DAY on denver_full_dpd (seed 0, as the plain headlines) and, for the all-hours model, NIGHT on denver_full_fill_night_dpd.
# First: retry the Denver all-hours training seed 100 (a24den_c4w_s1 hit a transient CUDA out-of-memory at 01:18) and its paired day verdict.
# Waits for the all-hours NM/TX export ([EXPA] done; it holds the 4.7 GB template file). One GPU job (B27). Log: data/l3.log [IL170]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [IL170] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
until grep -q '\[EXPA\] done' data/l3.log; do sleep 60; done
log start
A=data/train/denver_full_fill_all24_dpd.npz DD=data/train/denver_full_dpd.npz DN=data/train/denver_full_fill_night_dpd.npz
# ---- seed-100 retry
M=models/a24den_c4w_s1
[ -f $M.pt ] || { wait_ram; log "a24den_c4w_s1 train (retry)"; $PY -u -m tempest.generator.train --data $A --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_c4w_s1.toml > data/l3_train_a24den_c4w_s1.log 2>&1 && mv $M.pt.part $M.pt || log "FAILED a24den_c4w_s1 train"; }
if [ -f $M.pt ]; then
  [ -f $M.calib2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_a24den_c4w_s1.log 2>&1; }
  [ -f ${M}_cal2021_headline.csv ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $M.pt --data $DD --m 199 --first-test-year 2024 --last-test-year 2025 --calib $M.calib2021.npz --extras > data/l3_score_a24den_c4w_s1.log 2>&1 && log "a24den_c4w_s1 day scored"; }
  { echo "== $(date '+%F %T') IL170/A24 Denver all-hours C4w vs installed day model, DAY, training seed 100 (l3_blocal_c4w_s1 vs a24den_c4w_s1)"; $PY scripts/compare_headline.py models/l3_blocal_c4w_s1_cal2021_headline.csv ${M}_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
fi
# ---- post-processing for both Denver models
for spec in "l3_blocal_c4w $DD" "a24den_c4w $A"; do
  set -- $spec; C=models/$1 F=$2
  SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
  [ -f $SM ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $C.pt --data $F --calib $C.calib2021.npz --shuffle --full --template-cell 8 --out $SM > data/l3_il170_smap_$1.log 2>&1 && log "$1 shear map fitted" || log "FAILED $1 shear map"; }
  [ -f $LM ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $C.pt --data $F --calib $C.calib2021.npz --shear-map $SM --shuffle --template-cell 8 --out $LM > data/l3_il170_lmap_$1.log 2>&1 && log "$1 lapse map fitted" || log "FAILED $1 lapse map"; }
  P=models/il170_$1.pt; [ -f $P ] || cp $C.pt $P
  H=models/il170_$1_cal2021_smap_shufc8_lmap_headline.csv
  [ -f $H ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $DD --m 199 --first-test-year 2024 --last-test-year 2025 --mc --calib $C.calib2021.npz --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/l3_il170_$1_day.log 2>&1 && log "$1 stack day scored" || log "FAILED $1 stack day"; }
  { echo "== $(date '+%F %T') IL170 Denver $1: plain calibrated vs + shuffle c8 + shear map + lapse map, DAY"; $PY scripts/compare_headline.py models/$1_cal2021_headline.csv $H; echo "physics rows (stack):"; grep -E "superadiabatic|shear_gt|sfc_jump|coextreme,all" models/il170_$1_cal2021_smap_shufc8_lmap_mc.csv | sed 's/^/  /'; } >> data/l3_verdicts.txt 2>&1
done
P=models/il170_a24den_n.pt; [ -f $P ] || cp models/a24den_c4w.pt $P
C=models/a24den_c4w H=models/il170_a24den_n_cal2021_smap_shufc8_lmap_headline.csv
[ -f $H ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $DN --m 199 --first-test-year 2024 --last-test-year 2025 --mc --calib $C.calib2021.npz --shuffle --template-cell 8 --shear-map $C.shearmap2021_cell8.npz --lapse-map $C.lapsemap2021.npz > data/l3_il170_a24den_night.log 2>&1 && log "a24den stack night scored" || log "FAILED a24den stack night"; }
{ echo "== $(date '+%F %T') IL170 Denver all-hours: plain calibrated vs + shuffle c8 + shear map + lapse map, NIGHT"; $PY scripts/compare_headline.py models/a24den_alln_cal2021_headline.csv $H; } >> data/l3_verdicts.txt 2>&1
log done
