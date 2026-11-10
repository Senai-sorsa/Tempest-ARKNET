#!/bin/bash
# P6W (2026-11-10, handover item 2c): a C4w variant aimed by P6 (53 % of the wind-driven apogee spread comes from 50-150 m): the near-ground vector-wind term only up to 150 m
# (configs/generator_c4w_p6.toml, low_top_m 150; l3_c4w has 300). Same data and recipe as models/l3_c4w (the installed NM/TX all-hours model): pilot80_l21_all24_dpd, 1991-2023, own
# spread calibration, own shear map and lapse map (shuffle c8), scored as a stack paired with the l3_c4w stack: DAY 21-level seeds 0 / 1 (a24_all21_s0 / _s1 exist) and NIGHT (a24_allnight).
# Waits for the running full test suite and the Denver install ([DENPOST] audit done or FAILED). One GPU job (B27). Log: data/l3.log [P6W]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [P6W] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
until grep -qE '\[DENPOST\] (audit done|FAILED)' data/l3.log; do sleep 60; done
log start
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz
M=models/p6w_c4w
[ -f $M.pt ] || { wait_ram; log "train"; $PY -u -m tempest.generator.train --data $A21 --out $M.pt.part --max-year 2023 --min-year 1991 --config configs/generator_c4w_p6.toml > data/l3_train_p6w.log 2>&1 && mv $M.pt.part $M.pt || { log "FAILED train"; exit 2; }; }
[ -f $M.calib2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M.pt --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_p6w.log 2>&1 || { log "FAILED spread"; exit 2; }; }
[ -f $M.shearmap2021_cell8.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.shear_map --model $M.pt --data $A21 --calib $M.calib2021.npz --shuffle --full --template-cell 8 --out $M.shearmap2021_cell8.npz > data/l3_p6w_smap.log 2>&1 || { log "FAILED shear map"; exit 2; }; }
[ -f $M.lapsemap2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.lapse_map --model $M.pt --data $A21 --calib $M.calib2021.npz --shear-map $M.shearmap2021_cell8.npz --shuffle --template-cell 8 --out $M.lapsemap2021.npz > data/l3_p6w_lmap.log 2>&1 || { log "FAILED lapse map"; exit 2; }; }
H() { echo models/$1_cal2021_smap_shufc8_lmap_headline.csv; }
for spec in "p6w_d21_s0 $DA 0 a24_all21_s0" "p6w_d21_s1 $DA 1 a24_all21_s1" "p6w_night $NI 0 a24_allnight"; do
  set -- $spec; P=models/$1.pt; [ -f $P ] || cp $M.pt $P
  [ -f $(H $1) ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 --calib $M.calib2021.npz --shuffle --template-cell 8 \
    --shear-map $M.shearmap2021_cell8.npz --lapse-map $M.lapsemap2021.npz > data/l3_p6w_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; continue; }; }
  { echo "== $(date '+%F %T') P6W C4w to 300 m (installed l3_c4w) vs C4w to 150 m, $1"; $PY scripts/compare_headline.py $(H $4) $(H $1)
    echo "wind CRPS skill15 per height 10-300 m (base | new):"; $PY - "models/$4_cal2021_smap_shufc8_lmap.score.csv" "models/$1_cal2021_smap_shufc8_lmap.score.csv" <<'PYEOF'
import sys, pandas as pd
a, b = (pd.read_csv(f) for f in sys.argv[1:3])
for c in [c for c in a["column"] if c.split("_")[0] in ("u", "v") and c.split("_")[-1].isdigit() and int(c.split("_")[-1]) <= 300]:
    ra, rb = a[a.column == c].iloc[0], b[b.column == c].iloc[0]
    print(f"  {c:8s} {1 - ra.crps_unknown / ra.crps_clim:+.4f} | {1 - rb.crps_unknown / rb.crps_clim:+.4f}")
PYEOF
  } >> data/l3_verdicts.txt 2>&1
done
log done
