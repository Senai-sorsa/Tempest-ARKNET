#!/bin/bash
# C4w for a Denver-TRAINED model (2026-11-09): C4w helped in-box on NM/TX for two training seeds but hurt the zero-shot transfer to Denver; the Denver box's own trained model is the in-box
# case there. Reference: l3_blocal (p2f config on data/train/denver_full_dpd.npz, 1991-2023, calibration 2021-23, score 2024-25 --extras, ap_l3.sh) and its seed-100 twin l3_blocal_s1
# (the Denver training-seed tolerance). New: the same with configs/generator_c4w.toml (seed 0) and generator_c4w_s1.toml (seed 100), paired seed by seed. One runner (B27).
# Log: data/l3.log [DENLC4W]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/denver_full_dpd.npz
log() { echo "$(date '+%F %T') [DENLC4W] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
log start
for spec in "l3_blocal_c4w configs/generator_c4w.toml l3_blocal" "l3_blocal_c4w_s1 configs/generator_c4w_s1.toml l3_blocal_s1"; do
  set -- $spec; M=models/$1.pt C=models/$1.calib2021.npz H=models/$1_cal2021_headline.csv
  [ -f $M ] || { wait_ram; log "$1 train"; $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --min-year 1991 --config $2 > data/l3_train_$1.log 2>&1 && mv $M.part $M || { log "FAILED $1 train"; continue; }; }
  [ -f $C ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$1.log 2>&1 || { log "FAILED $1 spread"; continue; }; }
  [ -f $H ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/l3_score_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1 score"; continue; }; }
  { echo "== $(date '+%F %T') DENLC4W Denver-trained C4w vs Denver-trained p2f ($1 vs $3)"; $PY scripts/compare_headline.py models/$3_cal2021_headline.csv $H; } >> data/l3_verdicts.txt 2>&1
done
log done
