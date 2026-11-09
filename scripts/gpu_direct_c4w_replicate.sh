#!/bin/bash
# C4w replicate (2026-11-09), one sequential runner (B27: never two waiting queues). C4w (configs/generator_c4w.toml, the near-ground vector-wind term alone) beat the l21 stack on DAY seed 0
# (skill15 +0.0281 -> +0.0296, 0-1 km u +0.0064, RH 0-1 km +0.0005), but most of the gain sat ABOVE 1 km where the term does not act (v 1-18 km +0.004-0.005, sp +0.006): a training-seed
# effect is likely. Steps: (1) C4w scored on DAY seeds 1, 2 and NIGHT against the l21 stack (score-seed noise); (2) base p2f (generator_p2f_s1.toml) and C4w (generator_c4w_s1.toml) both
# retrained with training seed 100 on the same data, each with its own spread calibration and shear map, scored DAY seed 0 and paired (training-seed noise). Same recipe and rows as
# ap_l3_l21stack2.sh / ap_g_c4w.sh. Waits for >= 6 GB free RAM before each GPU step; steps skip when their output exists. Log: data/l3.log [C4WREP]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
log() { echo "$(date '+%F %T') [C4WREP] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
H() { echo models/$1_cal2021_smap_shufc8_headline.csv; }
score() {  # score STEM MODEL DATA SEED CALIB SMAP
  local P=models/$1.pt; [ -f $P ] || cp $2 $P; [ -f $(H $1) ] && return 0; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model $P --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $4 --calib $5 --shuffle --template-cell 8 --shear-map $6 > data/l3_c4wrep_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
}
verdict() { [ -f $(H $1) ] && [ -f $(H $2) ] && ! grep -q "C4WREP $3\$" data/l3_verdicts.txt && { echo "== $(date '+%F %T') C4WREP $3"; $PY scripts/compare_headline.py $(H $1) $(H $2)
  echo "physics rows ($1 | $2):"; grep -E "superadiabatic|shear_gt|sfc_jump" models/$1_cal2021_smap_shufc8_mc.csv | sed 's/^/  a /'; grep -E "superadiabatic|shear_gt|sfc_jump" models/$2_cal2021_smap_shufc8_mc.csv | sed 's/^/  b /'; } >> data/l3_verdicts.txt 2>&1; }
build() {  # build STEM CONFIG : train, spread calibration, shear map
  local M=models/$1
  if [ ! -f $M.pt ]; then wait_ram; log "$1 train"; $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2023 --min-year 1991 --config $2 > data/l3_train_$1.log 2>&1 && mv $M.pt.part $M.pt || { log "FAILED $1 train"; return 1; }; fi
  [ -f $M.calib2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$1.log 2>&1 || { log "FAILED $1 spread"; return 1; }; }
  [ -f $M.shearmap2021_cell8.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $A21 --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_smap_$1.log 2>&1 || { log "FAILED $1 smap"; return 1; }; }
}
log start
C=models/l3_c4w
for s in 1 2; do score l3_c4w_s$s $C.pt $DA $s $C.calib2021.npz $C.shearmap2021_cell8.npz; verdict l3_s21l21_s$s l3_c4w_s$s "C4w vs l21 stack DAY score seed $s"; done
score l3_c4w_night $C.pt $NI 0 $C.calib2021.npz $C.shearmap2021_cell8.npz; verdict l3_s21l21_night l3_c4w_night "C4w vs l21 stack NIGHT"
build l3_h_l21_t100 configs/generator_p2f_s1.toml && score l3_h_l21_t100_s0 models/l3_h_l21_t100.pt $DA 0 models/l3_h_l21_t100.calib2021.npz models/l3_h_l21_t100.shearmap2021_cell8.npz
build l3_c4w_t100 configs/generator_c4w_s1.toml && score l3_c4w_t100_s0 models/l3_c4w_t100.pt $DA 0 models/l3_c4w_t100.calib2021.npz models/l3_c4w_t100.shearmap2021_cell8.npz
verdict l3_h_l21_t100_s0 l3_c4w_t100_s0 "C4w vs base, both training seed 100, DAY score seed 0"
verdict l3_s21l21_s0 l3_h_l21_t100_s0 "base training seed 0 vs base training seed 100 (training-seed noise), DAY score seed 0"
log done
