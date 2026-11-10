#!/bin/bash
# FRESH ONE-TIME FINAL TEST, 2026 July-October (user approval 2026-11-09, ASK_LATER 14; the 2026 January-June test was spent on 2026-11-06). Runs ONCE: lock file
# data/FINAL_TEST_2026H2_DONE. Needs: CONFIRM_FINAL=yes bash scripts/final_test_2026h2.sh, and all 16 GRIB files of scripts/fetch_final_window.py in data/raw/era5_2026h2.
# Nothing in it was chosen with these months: the flags are fixed below BEFORE the first run (the shipped stacks), the indices for October carry the last known WWV (September)
# forward, which is what the tool does for any future query.
# Scored: (1) the CURRENT tool model (generator_80_c4w + calibration + shuffle c8 + shear map + lapse map, the bundled assets since 2026-11-09), (2) the PREVIOUS tool model
# (generator_80_p2f + calibration + shuffle c8 + shear map, the bundle before), each with the 15-year climatology and the Gaussian (Earth-GRAM-style) baseline in the same headline,
# on ERA5-type targets of July-October 2026 (5,000 random held-out rows, the scorer default used by every development score and the first final test; more rows do not fit in RAM: N x 199 x 179 floats per array) and on the July-October 2026 balloons of Santa Teresa and Midland (balloon scorer: no lapse-map option, so both models without it).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
[ "$CONFIRM_FINAL" = "yes" ] || { echo "set CONFIRM_FINAL=yes to run the one-time 2026 July-October final test"; exit 2; }
[ -f data/FINAL_TEST_2026H2_DONE ] && { echo "the 2026 July-October final test was already run: $(cat data/FINAL_TEST_2026H2_DONE)"; exit 3; }
for m in 202607 202608 202609 202610; do for k in pl1 pl2 pl3 sfc; do [ -f data/raw/era5_2026h2/${k}_$m.grib ] || { echo "missing data/raw/era5_2026h2/${k}_$m.grib"; exit 4; }; done; done
. scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
OUT=docs/final_test_2026h2; mkdir -p $OUT
PROF=data/pilot/profiles_2026h2.zarr PART=data/train/final_2026h2_part.npz D=data/train/final_2026h2_dpd.npz IND=data/raw/indices_2026h2
# --- data (before the lock: rebuilding them is not a test) ---
[ -d data/raw/era5_em_2026h2/sp.zarr ] || $PY -W ignore scripts/convert_2026h2.py > $OUT/convert.log 2>&1 || { echo "FAILED convert"; exit 5; }
if [ ! -d $IND ]; then
  mkdir -p $IND && cp data/raw/indices/* $IND/ && $PY - "$IND/wwv.txt" <<'PYEOF' || { echo "FAILED indices"; exit 5; }
import sys
p = sys.argv[1]
lines = [l for l in open(p, encoding="utf-8").read().splitlines() if l.strip()]
have = {l.split()[0] for l in lines if l.split() and l.split()[0].isdigit()}
last = [l for l in lines if l.split() and l.split()[0].isdigit()][-1]
for ym in ("202607", "202608", "202609", "202610"):
    if ym not in have:
        lines.append(ym + last[len(last.split()[0]):])
        print("carried WWV forward to", ym)
open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYEOF
fi
[ -d $PROF ] || $PY -W ignore -u -m tempest.profiles.to_heights --raw data/raw/era5_em_2026h2 --cds data/raw/era5_cds_2026h2 --out $PROF --first-year 2026 > $OUT/to_heights.log 2>&1 || { echo "FAILED to_heights"; exit 5; }
[ -f $PART ] || $PY -W ignore -u -m tempest.generator.build_dataset --profiles $PROF --indices $IND --out $PART --first-year 2026 --last-year 2026 --station-map models/station_map_mix.npz --features base --rh-target dpd > $OUT/build.log 2>&1 || { echo "FAILED build"; exit 5; }
if [ ! -f $D ]; then
  $PY - <<'PYEOF' > $OUT/join.log 2>&1 || { echo "FAILED join"; exit 5; }
import numpy as np
from tempest.generator.train import load_npz
a, b = load_npz("data/train/pilot80_dpd.npz"), load_npz("data/train/final_2026h2_part.npz")
for k in ("cond_names", "target_names", "rh_target"):
    assert np.array_equal(np.asarray(a[k]), np.asarray(b[k])), k
keep = np.flatnonzero(np.asarray(a["year"]) <= 2025)            # the 2026 January-June rows were the first final test: left out, so test year 2026 = July-October only
out = {k: np.concatenate([np.asarray(a[k][keep]), np.asarray(b[k])]) for k in ("cond", "target", "year")}
print(f"training-file rows <= 2025: {len(keep):,}; 2026 July-October rows: {len(b['year']):,}")
np.savez("data/train/final_2026h2_dpd.npz", **out, cond_names=np.asarray(a["cond_names"]), target_names=np.asarray(a["target_names"]), rh_target=np.asarray(a["rh_target"]))
PYEOF
fi
# --- the one-time scoring ---
echo "started $(date '+%F %T')" > data/FINAL_TEST_2026H2_DONE
N=models/generator_80_c4w P=models/generator_80_p2f
cp $N.pt models/ft26_c4w.pt; cp $P.pt models/ft26_p2f.pt
$PY -W ignore -u -m tempest.scoring.score --model models/ft26_c4w.pt --data $D --m 199 --first-test-year 2026 --last-test-year 2026 --mc --extras --calib $N.calib2021.npz \
  --shuffle --template-cell 8 --shear-map $N.shearmap2021_cell8.npz --lapse-map $N.lapsemap2021.npz > $OUT/era5_c4w.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model models/ft26_p2f.pt --data $D --m 199 --first-test-year 2026 --last-test-year 2026 --mc --extras --calib $P.calib2021.npz \
  --shuffle --template-cell 8 --shear-map $P.shearmap2021_cell8.npz > $OUT/era5_p2f.log 2>&1
for X in c4w p2f; do M=models/generator_80_$X
  $PY -W ignore -u -m tempest.scoring.sonde --model models/ft26_$X.pt --data $D --profiles data/pilot/profiles80.zarr --igra data/raw/igra_2026 --m 199 --first-test-year 2026 --last-test-year 2026 \
    --first-test-month 7 --calib $M.calib2021.npz --shear-map $M.shearmap2021_cell8.npz --extras > $OUT/sonde_$X.log 2>&1
done
echo "finished $(date '+%F %T')" >> data/FINAL_TEST_2026H2_DONE
mkdir -p $OUT/headlines; cp models/ft26_*headline.csv $OUT/headlines/ 2>/dev/null
$PY scripts/compare_headline.py models/ft26_p2f_cal2021_smap_shufc8_headline.csv models/ft26_c4w_cal2021_smap_shufc8_lmap_headline.csv > $OUT/compare_era5.txt 2>&1
echo "done: logs and headlines in $OUT"
