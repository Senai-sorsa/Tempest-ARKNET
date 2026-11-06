#!/bin/bash
# GROUP E4: the single 2026 January-June test. Runs ONCE (lock file data/FINAL_TEST_DONE). Needs: CONFIRM_FINAL=yes bash scripts/final_test.sh
# What is scored: the final climate-generator system (p2f + range map + the kept shape stack) on ERA5-type targets of 2026 H1 (85,734 dataset rows), on the 2026 IGRA balloons (data/raw/igra_2026),
# the E12 baseline (b0smix, its own dataset) and the Gaussian (Earth-GRAM-style) baseline with the same code (they are columns of the same score files), and the shape diagnostics.
# Mode F is NOT scored here: the archived HRES forecasts end 2023-01 (its test year is 2022). Nothing is tuned on these rows: no flag below was chosen with 2026 data.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
[ "$CONFIRM_FINAL" = "yes" ] || { echo "set CONFIRM_FINAL=yes to run the one-time final test"; exit 2; }
[ -f data/FINAL_TEST_DONE ] && { echo "the final test was already run: $(cat data/FINAL_TEST_DONE)"; exit 3; }
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
B=models/generator_80_p2f; M=$B.pt; C=$B.calib2021.npz; D=data/train/pilot80_dpd.npz; P=data/pilot/profiles80.zarr
# --- the flag set chosen by IL-16 on 2024-25 (edit ONLY before the first run) ---
ERA5_FLAGS="--shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz"
SONDE_FLAGS="--shear-map $B.shearmap2021_cell8.npz"
SHAPE_FLAGS="--shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz"
echo "started $(date '+%F %T')" > data/FINAL_TEST_DONE
OUT=docs/final_test; mkdir -p $OUT/dev_backup
cp models/generator_80_p2f*_headline.csv models/generator_80_b0smix*_headline.csv $OUT/dev_backup/ 2>/dev/null   # the scorers write to the same file names for any test year: keep the 2024-25 development tables
$PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2026 --last-test-year 2026 --calib $C $ERA5_FLAGS --extras > $OUT/era5_final.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --igra data/raw/igra_2026 --m 199 --first-test-year 2026 --last-test-year 2026 --calib $C --extras $SONDE_FLAGS > $OUT/sonde_final.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model models/generator_80_b0smix.pt --data data/train/pilot80_smix.npz --m 199 --first-test-year 2026 --last-test-year 2026 --calib models/generator_80_b0smix.calib2021.npz --extras > $OUT/era5_e12.log 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model models/generator_80_b0smix.pt --data data/train/pilot80_smix.npz --profiles $P --igra data/raw/igra_2026 --m 199 --first-test-year 2026 --last-test-year 2026 --calib models/generator_80_b0smix.calib2021.npz --extras > $OUT/sonde_e12.log 2>&1
$PY -W ignore scripts/diagnose.py $M $C $D --first-year 2026 --last-year 2026 $SHAPE_FLAGS --out $OUT/final_shape > $OUT/shape_final.log 2>&1
echo "finished $(date '+%F %T')" >> data/FINAL_TEST_DONE
mkdir -p $OUT/final_headlines; cp models/generator_80_p2f*_headline.csv models/generator_80_b0smix*_headline.csv $OUT/final_headlines/
echo "logs in $OUT; the 2026 headline tables are in $OUT/final_headlines (the 2024-25 ones in $OUT/dev_backup). Now write docs/results/FINAL_REPORT.md (E5)."
