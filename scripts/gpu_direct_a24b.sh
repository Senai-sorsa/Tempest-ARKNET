#!/bin/bash
# A24b (2026-11-10): the ERA5 verdict on the all-hours NM/TX stack depends on which ERA5 is the truth (13-level: -0.0006 / -0.0016; 21-level: +0.0044 / +0.0053), and each model
# was trained on its own kind (B30). Independent referee: IGRA balloons EPZ + MAF, 2024-25, at 00Z (about 17 h solar) AND 12Z (about 05 h solar, night; new opt-in sonde --hour 12).
# Shipped day model (generator_80_c4w) vs all-hours model (l3_c4w), each with its own range map and shear map (the balloon scorer has no shuffle / lapse map: same for both, paired).
# Waits for the post-A24 test run ([TESTS] done after A24). Log: data/l3.log [A24B]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [A24B] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
until grep -q '\[TESTS\] done after A24' data/l3.log; do sleep 60; done
log start
for H in 0 12; do
  for spec in "a24b_ship generator_80_c4w" "a24b_all l3_c4w"; do
    set -- $spec; P=models/$1.pt; [ -f $P ] || cp models/$2.pt $P
    while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done
    $PY -W ignore -u -m tempest.scoring.sonde --model $P --data data/train/pilot80_dpd.npz --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 \
      --calib models/$2.calib2021.npz --shear-map models/$2.shearmap2021_cell8.npz --hour $H > data/l3_a24b_$1_h$H.log 2>&1 && log "$1 hour $H scored" || log "FAILED $1 hour $H"
  done
  S=$([ $H = 12 ] && echo _12z || echo "")
  { echo "== $(date '+%F %T') A24B balloons EPZ + MAF 2024-25 at ${H}Z: shipped day model vs all-hours model"; $PY scripts/compare_headline.py models/a24b_ship_sonde_cal2021_smap${S}_headline.csv models/a24b_all_sonde_cal2021_smap${S}_headline.csv; } >> data/l3_verdicts.txt 2>&1
done
log done
