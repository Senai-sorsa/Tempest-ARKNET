#!/bin/bash
# Second training seed of the shipped-model pair (2026-11-09): generator_80_p2f vs generator_80_c4w were compared with ONE training seed (NM/TX +0.0013-0.0016 on 3 score seeds; Denver
# zero-shot -0.0016, temperature worse). Retrain BOTH with training seed 100 (configs/generator_p2f_s1.toml, generator_c4w_s1.toml) on data/train/pilot80_dpd.npz, 1991-2023, build each
# stack (spread calibration 2021-23, shear map, shuffle c8, lapse map), score NM/TX DAY seed 0 (pilot80_dpd) and Denver zero-shot (trust fitted on Denver 2021-23, day), and pair them.
# One runner (B27). Waits for >= 8 GB free RAM before each GPU step. Log: data/l3.log [T100X]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz
log() { echo "$(date '+%F %T') [T100X] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
build() {  # build STEM CONFIG
  local M=models/$1
  if [ ! -f $M.pt ]; then wait_ram; log "$1 train"; $PY -u -m tempest.generator.train --data $D --out $M.pt.part --max-year 2023 --min-year 1991 --config $2 > data/l3_train_$1.log 2>&1 && mv $M.pt.part $M.pt || { log "FAILED $1 train"; return 1; }; fi
  [ -f $M.calib2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$1.log 2>&1 || { log "FAILED $1 spread"; return 1; }; }
  [ -f $M.shearmap2021_cell8.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $D --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_smap_$1.log 2>&1 || { log "FAILED $1 smap"; return 1; }; }
  [ -f $M.lapsemap2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $M.pt --data $D --calib $M.calib2021.npz --shear-map $M.shearmap2021_cell8.npz --shuffle --template-cell 8 --out $M.lapsemap2021.npz > data/l3_lmap_$1.log 2>&1 || { log "FAILED $1 lmap"; return 1; }; }
  local S=models/$1_s0; [ -f $S.pt ] || cp $M.pt $S.pt
  [ -f ${S}_cal2021_smap_shufc8_lmap_headline.csv ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $S.pt --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $M.calib2021.npz --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz --lapse-map $M.lapsemap2021.npz > data/l3_score_$1.log 2>&1 && log "$1 NM/TX scored" || log "FAILED $1 score"; }
  local P=models/$1_den; [ -f $P.pt ] || cp $M.pt $P.pt
  [ -f $P.trust2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.trust --model $P.pt --data $DEN --calib $M.calib2021.npz --from-year 2021 --year 2023 --m 199 > data/l3_trust_$1.log 2>&1 || { log "FAILED $1 trust"; return 1; }; }
  [ -f ${P}_cal2021_trust_smap_shufc8_headline.csv ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --model $P.pt --data $DEN --calib $M.calib2021.npz --trust $P.trust2021.npz --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz > data/l3_dscore_$1.log 2>&1 && log "$1 Denver scored" || log "FAILED $1 Denver score"; }
}
log start
build generator_80_p2f_t100 configs/generator_p2f_s1.toml
build generator_80_c4w_t100 configs/generator_c4w_s1.toml
a=models/generator_80_p2f_t100 b=models/generator_80_c4w_t100
[ -f ${a}_s0_cal2021_smap_shufc8_lmap_headline.csv ] && [ -f ${b}_s0_cal2021_smap_shufc8_lmap_headline.csv ] && { echo "== $(date '+%F %T') T100X shipped-model C4w vs p2f, both training seed 100, + lapse map, NM/TX DAY seed 0"; $PY scripts/compare_headline.py ${a}_s0_cal2021_smap_shufc8_lmap_headline.csv ${b}_s0_cal2021_smap_shufc8_lmap_headline.csv; } >> data/l3_verdicts.txt 2>&1
[ -f ${a}_den_cal2021_trust_smap_shufc8_headline.csv ] && [ -f ${b}_den_cal2021_trust_smap_shufc8_headline.csv ] && { echo "== $(date '+%F %T') T100X Denver zero-shot C4w vs p2f, both training seed 100, + Denver trust (day)"; $PY scripts/compare_headline.py ${a}_den_cal2021_trust_smap_shufc8_headline.csv ${b}_den_cal2021_trust_smap_shufc8_headline.csv; } >> data/l3_verdicts.txt 2>&1
log done
