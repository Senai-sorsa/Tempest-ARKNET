#!/bin/bash
# Direct sequential runner (2026-11-09): ap_g_c4w.sh and ap_g_lmap80.sh wait on each other (each one's "another queue" pattern matches the other: mistake B27), and stopping either was
# refused by the permission check. This runs the SAME steps with the SAME output names, one GPU job at a time: L21b lapse map on the shipped stack + its two scores, then C4w train /
# calibrate / shear map / score. A stuck queue that is later released finds the outputs and skips its steps. Waits for >= 6 GB free RAM before each GPU step. Log: data/l3.log [DIRECT].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [DIRECT] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
log start
# ---- L21b: lapse map on the shipped stack
D=data/train/pilot80_dpd.npz B=models/generator_80_p2f CAL=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz LM=$B.lapsemap2021.npz
if [ ! -f $LM ]; then wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $B.pt --data $D --calib $CAL --shear-map $SM --shuffle --template-cell 8 --out $LM > data/l3_lmap80_fit.log 2>&1 && log "lmap80 fitted" || log "FAILED lmap80 fit"; fi
H0=models/g80lm_base_s0_cal2021_smap_shufc8_headline.csv H1=models/g80lm_lmap_s0_cal2021_smap_shufc8_lmap_headline.csv
for spec in "g80lm_base_s0 $H0" "g80lm_lmap_s0 $H1 --lapse-map $LM"; do
  set -- $spec; P=models/$1.pt; [ -f $P ] || cp $B.pt $P
  if [ ! -f $2 ] && [ -f $LM ]; then wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 \
      --calib $CAL --shuffle --template-cell 8 --shear-map $SM "${@:3}" > data/l3_lmap80_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"; fi
done
[ -f $H0 ] && [ -f $H1 ] && ! grep -q "LMAP80 shipped stack" data/l3_verdicts.txt && { echo "== $(date '+%F %T') LMAP80 shipped stack + lapse map vs shipped stack, seed 0 (pilot80_dpd)"; $PY scripts/compare_headline.py $H0 $H1
  echo "physics rows (base | lapse map):"; grep -E "superadiabatic|shear_gt|sfc_jump" ${H0%_headline.csv}_mc.csv | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" ${H1%_headline.csv}_mc.csv | sed 's/^/  lmap /'; } >> data/l3_verdicts.txt 2>&1
# ---- C4w
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz M=models/l3_c4w BS=models/l3_s21l21_s0
if [ ! -f $M.pt ]; then wait_ram; log "c4w train"; $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_c4w.toml > data/l3_train_c4w.log 2>&1 && mv $M.pt.part $M.pt || log "FAILED c4w train"; fi
[ -f $M.pt ] && [ ! -f $M.calib2021.npz ] && { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_c4w.log 2>&1 || log "FAILED c4w spread"; }
[ -f $M.calib2021.npz ] && [ ! -f $M.shearmap2021_cell8.npz ] && { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $A21 --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_c4w_smap.log 2>&1 || log "FAILED c4w smap"; }
HC=${M}_s0_cal2021_smap_shufc8_headline.csv
if [ -f $M.shearmap2021_cell8.npz ] && [ ! -f $HC ]; then cp $M.pt ${M}_s0.pt; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model ${M}_s0.pt --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $M.calib2021.npz --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz > data/l3_score_c4w.log 2>&1 && log "c4w scored" || log "FAILED c4w score"; fi
[ -f $HC ] && ! grep -q "C4w (wind term only)" data/l3_verdicts.txt && { echo "== $(date '+%F %T') C4w (wind term only) vs l21 stack seed 0 (DAY)"; $PY scripts/compare_headline.py ${BS}_cal2021_smap_shufc8_headline.csv $HC
  echo "physics rows (base | c4w):"; grep -E "superadiabatic|shear_gt|sfc_jump" ${BS}_cal2021_smap_shufc8_mc.csv | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" ${M}_s0_cal2021_smap_shufc8_mc.csv | sed "s/^/  c4w  /"; } >> data/l3_verdicts.txt 2>&1
log done
