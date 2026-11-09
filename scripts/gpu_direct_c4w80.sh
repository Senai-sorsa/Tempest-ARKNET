#!/bin/bash
# C4w for the SHIPPED model (2026-11-09): C4w (configs/generator_c4w.toml = p2f + the near-ground vector-wind term) was confirmed on the l21 data by a training-seed pair (+0.0015 / +0.0032
# mean skill15). The tool runs models/generator_80_p2f (p2f on data/train/pilot80_dpd.npz, 1991-2023). This retrains that model with the C4w config on the same data and builds the full
# shipped stack (spread calibration 2021-23, shear map, shuffle c8, lapse map), then scores DAY seed 0 (--mc) against the shipped stack + lapse map (models/g80lm_lmap_s0, L21b) on the same
# rows. If it passes it is the candidate tool model for Group E (export_final.sh with --model models/generator_80_c4w). Chained after gpu_direct_l21_stack.sh by its "[L21S] done" line
# (no queue pattern, B27). Waits for >= 8 GB free RAM before each GPU step. Log: data/l3.log [C4W80]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz M=models/generator_80_c4w
log() { echo "$(date '+%F %T') [C4W80] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
until grep -q '\[L21S\] done' data/l3.log; do sleep 60; done
log start
if [ ! -f $M.pt ]; then wait_ram; log "train"; $PY -u -m tempest.generator.train --data $D --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_c4w.toml > data/l3_train_c4w80.log 2>&1 && mv $M.pt.part $M.pt || { log "FAILED train"; exit 2; }; fi
[ -f $M.calib2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_c4w80.log 2>&1 || { log "FAILED spread"; exit 3; }; }
[ -f $M.shearmap2021_cell8.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $D --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_smap_c4w80.log 2>&1 || { log "FAILED smap"; exit 4; }; }
[ -f $M.lapsemap2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $M.pt --data $D --calib $M.calib2021.npz --shear-map $M.shearmap2021_cell8.npz --shuffle --template-cell 8 --out $M.lapsemap2021.npz > data/l3_lmap_c4w80.log 2>&1 || { log "FAILED lapse map"; exit 5; }; }
log "stack built"
S=models/g80c4w_s0 H1=models/g80c4w_s0_cal2021_smap_shufc8_lmap_headline.csv H0=models/g80lm_lmap_s0_cal2021_smap_shufc8_lmap_headline.csv
[ -f $S.pt ] || cp $M.pt $S.pt
if [ ! -f $H1 ]; then wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $S.pt --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 --calib $M.calib2021.npz --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz --lapse-map $M.lapsemap2021.npz > data/l3_score_c4w80.log 2>&1 && log "scored" || log "FAILED score"; fi
[ -f $H0 ] && [ -f $H1 ] && { echo "== $(date '+%F %T') C4W80 shipped-model retrain with C4w + its stack + lapse map vs shipped stack + lapse map, DAY seed 0 (pilot80_dpd)"; $PY scripts/compare_headline.py $H0 $H1
  echo "physics rows (shipped + lmap | c4w80 + lmap):"; grep -E "superadiabatic|shear_gt|sfc_jump" ${H0%_headline.csv}_mc.csv | sed 's/^/  a /'; grep -E "superadiabatic|shear_gt|sfc_jump" ${H1%_headline.csv}_mc.csv | sed 's/^/  b /'; } >> data/l3_verdicts.txt 2>&1
log done
