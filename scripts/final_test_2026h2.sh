#!/bin/bash
# FRESH ONE-TIME FINAL TEST, 2026 July-October (user approval 2026-11-09, ASK_LATER 14; the 2026 January-June test was spent on 2026-11-06). Run it only when the user says the
# model is FINAL (user 2026-11-09 23:30), never just because the data has arrived. Runs ONCE: lock file
# data/FINAL_TEST_2026H2_DONE. Needs: CONFIRM_FINAL=yes bash scripts/final_test_2026h2.sh, and all 16 GRIB files of scripts/fetch_final_window.py in data/raw/era5_2026h2.
# Nothing in it was chosen with these months: the flags are fixed below BEFORE the first run (the shipped stacks), the indices for October carry the last known WWV (September)
# forward, which is what the tool does for any future query.
# 2026-11-14 audit fix: the CURRENT tool model is models/l3_c4w (the sha256 in tempest_weather/assets/manifest.json, checked below before the lock), not generator_80_c4w (sha 7ab6df26,
# never shipped). It was trained on the 21-level all-hours-store recipe (pilot80_l21_day_dpd: station_map_mix, base features, dpd, --all-hours), so it is scored (1a) on its own recipe
# (training rows <= 2025 from pilot80_l21_day_dpd + 2026 July-October rows built with --all-hours) = its headline, and (1b) on the SAME rows as the previous model (file D below) for the
# paired current-vs-previous comparison.
# Scored: (1) the CURRENT tool model (l3_c4w + calibration + shuffle c8 + shear map + lapse map, the bundled assets since 2026-11-10), (2) the PREVIOUS tool model
# (generator_80_p2f + calibration + shuffle c8 + shear map, the bundle before), each with the 15-year climatology and the Gaussian (Earth-GRAM-style) baseline in the same headline,
# 2026-11-21 FREEZE REPOINT (New_Plan 28.5, user go 2026-11-21): the CURRENT model is now the frozen final stack, models/s25/c4wx4r_s0 (shipped l3_c4w weights + X4-R table,
# variant e, k 3) with its own refits (calib2021 = spread fit 2021-23, _smap_cell8, _lmap_cell8), checked against tempest_weather/assets_final_2026h2/manifest.json. Same recipe rows
# (D21 / D) and the same PREVIOUS model as before. Tool-only parts are not in the scorers: AV35 aloft map (checked on balloons by b88), WD1 ur5 (sequences only), NOW2, O3, AV13.
# DRY_RUN=1 bash scripts/final_test_2026h2.sh = every guard and file check, then prints the scoring plan; no data build, no lock, no scoring.
# on ERA5-type targets of July-October 2026 (5,000 random held-out rows, the scorer default used by every development score and the first final test; more rows do not fit in RAM: N x 199 x 179 floats per array) and on the July-October 2026 balloons of Santa Teresa and Midland (balloon scorer: no lapse-map option, so both models without it).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
[ "$CONFIRM_FINAL" = "yes" ] || [ "$DRY_RUN" = "1" ] || { echo "set CONFIRM_FINAL=yes to run the one-time 2026 July-October final test"; exit 2; }
[ -f data/FINAL_TEST_2026H2_DONE ] && { echo "the 2026 July-October final test was already run: $(cat data/FINAL_TEST_2026H2_DONE)"; exit 3; }
for m in 202607 202608 202609 202610; do for k in pl1 pl2 pl3 sfc; do [ -f data/raw/era5_2026h2/${k}_$m.grib ] || { echo "missing data/raw/era5_2026h2/${k}_$m.grib"; exit 4; }; done; done
. scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
OUT=docs/final_test_2026h2; mkdir -p $OUT
PROF=data/pilot/profiles_2026h2.zarr PART=data/train/final_2026h2_part.npz D=data/train/final_2026h2_dpd.npz IND=data/raw/indices_2026h2
PART21=data/train/final_2026h2_l21_part.npz D21=data/train/final_2026h2_l21_dpd.npz
N=models/s25/c4wx4r_s0 P=models/generator_80_p2f
NSM=${N}_smap_cell8.npz NLM=${N}_lmap_cell8.npz PSM=$P.shearmap2021_cell8.npz
FROZEN=tempest_weather/assets_final_2026h2/manifest.json
[ -f $FROZEN ] || { echo "missing $FROZEN: run the 28.5 freeze (scripts/freeze_2026h2.sh) first"; exit 6; }
want=$($PY -c "import json; print(json.load(open('$FROZEN', encoding='utf-8'))['source_sha256'])")
[ "$(sha256sum $N.pt | cut -d' ' -f1)" = "$want" ] || { echo "$N.pt is not the frozen final model (manifest source_sha256 $want)"; exit 6; }
wantc=$($PY -c "import json; print(json.load(open('$FROZEN', encoding='utf-8'))['calib_sha256'])")
[ "$(sha256sum $N.calib2021.npz | cut -d' ' -f1)" = "$wantc" ] || { echo "$N.calib2021.npz is not the frozen calibration (manifest calib_sha256 $wantc)"; exit 6; }
$PY - "$N.calib2021.npz" <<'PYEOF' || { echo "calibration fitted on 2026 data"; exit 6; }
import sys, numpy as np
c = np.load(sys.argv[1]); assert "fit_year" in c.files and int(c["fit_year"]) < 2026, "fit_year"
PYEOF
for f in $N.calib2021.npz $NSM $NLM $P.calib2021.npz $PSM data/train/pilot80_l21_day_dpd.npz data/train/pilot80_dpd.npz; do [ -f $f ] || { echo "missing $f"; exit 6; }; done
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY RUN ok: guards passed (16 GRIBs, frozen model + calibration sha, calibration fit year < 2026, all inputs present); lock $( [ -f data/FINAL_TEST_2026H2_DONE ] && echo PRESENT || echo absent )"
  echo "would score: CURRENT $N (calib $N.calib2021.npz, shuffle c8, $NSM, $NLM) on $D21 and $D; PREVIOUS $P ($P.calib2021.npz, shuffle c8, $PSM) on $D; sondes both; then compare_headline"
  exit 0
fi
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
  # 28.14 mistake hunt (run 2): ONI SON 2026 (= October) is published only in December; without it every October row was dropped as an index gap.
  # Carry the last season (ASO) forward, like WWV above (an approximation of the known October driver; the unknown-driver headline does not use it).
  $PY - "$IND/oni.txt" <<'PYEOF' || { echo "FAILED oni"; exit 5; }
import sys
p = sys.argv[1]
lines = [l for l in open(p, encoding="utf-8").read().splitlines() if l.strip()]
if not any(l.split()[:2] == ["SON", "2026"] for l in lines):
    last = lines[-1].split()
    assert last[:2] == ["ASO", "2026"], last
    lines.append(f"  SON 2026  {last[2]}   {last[3]}")
    print("carried ONI ASO 2026 forward to SON 2026 (October)")
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
# the current model's own recipe (2026-11-14): 2026 rows with --all-hours from the same store, joined with pilot80_l21_day_dpd rows <= 2025
[ -f $PART21 ] || $PY -W ignore -u -m tempest.generator.build_dataset --profiles $PROF --indices $IND --out $PART21 --first-year 2026 --last-year 2026 --station-map models/station_map_mix.npz --features base --rh-target dpd --all-hours > $OUT/build_l21.log 2>&1 || { echo "FAILED build l21"; exit 5; }
if [ ! -f $D21 ]; then
  $PY - <<'PYEOF' > $OUT/join_l21.log 2>&1 || { echo "FAILED join l21"; exit 5; }
import numpy as np
from tempest.generator.train import load_npz
a, b = load_npz("data/train/pilot80_l21_day_dpd.npz"), load_npz("data/train/final_2026h2_l21_part.npz")
for k in ("cond_names", "target_names", "rh_target"):
    assert np.array_equal(np.asarray(a[k]), np.asarray(b[k])), k
keep = np.flatnonzero(np.asarray(a["year"]) <= 2025)
out = {k: np.concatenate([np.asarray(a[k][keep]), np.asarray(b[k])]) for k in ("cond", "target", "year")}
print(f"l21 training-file rows <= 2025: {len(keep):,}; 2026 July-October rows (all-hours store): {len(b['year']):,}")
np.savez("data/train/final_2026h2_l21_dpd.npz", **out, cond_names=np.asarray(a["cond_names"]), target_names=np.asarray(a["target_names"]), rh_target=np.asarray(a["rh_target"]))
PYEOF
fi
# --- the one-time scoring ---
echo "started $(date '+%F %T')" > data/FINAL_TEST_2026H2_DONE
cp $N.pt models/ft26_c4w.pt; cp $N.pt models/ft26_c4wp.pt; cp $P.pt models/ft26_p2f.pt
$PY -W ignore -u -m tempest.scoring.score --model models/ft26_c4w.pt --data $D21 --m 199 --first-test-year 2026 --last-test-year 2026 --mc --extras --calib $N.calib2021.npz \
  --shuffle --template-cell 8 --shear-map $NSM --lapse-map $NLM > $OUT/era5_c4w.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model models/ft26_c4wp.pt --data $D --m 199 --first-test-year 2026 --last-test-year 2026 --calib $N.calib2021.npz \
  --shuffle --template-cell 8 --shear-map $NSM --lapse-map $NLM > $OUT/era5_c4w_samerows.log 2>&1
$PY -W ignore -u -m tempest.scoring.score --model models/ft26_p2f.pt --data $D --m 199 --first-test-year 2026 --last-test-year 2026 --mc --extras --calib $P.calib2021.npz \
  --shuffle --template-cell 8 --shear-map $PSM > $OUT/era5_p2f.log 2>&1
for X in c4w p2f; do M=$([ $X = c4w ] && echo $N || echo $P); SM=$([ $X = c4w ] && echo $NSM || echo $PSM)
  $PY -W ignore -u -m tempest.scoring.sonde --model models/ft26_$X.pt --data $D --profiles data/pilot/profiles80.zarr --igra data/raw/igra_2026 --m 199 --first-test-year 2026 --last-test-year 2026 \
    --first-test-month 7 --last-test-month 10 --indices $IND --calib $M.calib2021.npz --shear-map $SM --extras > $OUT/sonde_$X.log 2>&1
done
echo "finished $(date '+%F %T')" >> data/FINAL_TEST_2026H2_DONE
mkdir -p $OUT/headlines; cp models/ft26_*headline.csv $OUT/headlines/ 2>/dev/null
$PY scripts/compare_headline.py models/ft26_p2f_cal2021_smap_shufc8_fair_headline.csv models/ft26_c4wp_cal2021_smap_shufc8_lmap_fair_headline.csv > $OUT/compare_era5.txt 2>&1   # same rows (file D)
echo "done: logs and headlines in $OUT"
