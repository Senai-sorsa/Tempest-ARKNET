#!/bin/bash
# G2 eight North-American boxes, leave-one-box-out (docs/plans/GLOBAL_PLAN.md G2).
# Usage: scripts/global/g2.sh [CANDIDATES] [SEEDS]      default "global studt siren sirenstudt" "0"
#   (1) per new box: ERA5 columns -> heights (all hours) -> training rows (plain ERA5, dpd, fill-top)
#   (2) eight boxes joined with row_group = box id (0 nmtx, 1 denver, 2.. the six new boxes)
#   (3) climatological tropopause column (needs data/raw/era5_global; skipped with a log line otherwise)
#   (4) per candidate config and seed: one pooled model (in-sample check) + one model per left-out box
#       (train, spread calibration 2021-23 and scoring 2024-25 never see the left-out box)
#   (5) gate: python -m tempest.scoring.spatial gate-g2 -> results/G2/gate_g2_<cand>_s<seed>.csv
# Resume: rerun the same command; finished steps are skipped (results/G2/*.done).
G=G2; . "$(dirname "$0")/g_common.sh"
CANDS=${1:-global studt siren sirenstudt}; SEEDS=${2:-0}
NEW="vandenberg canaveral fairbanks saltlake lamont hilo"
NT=data/train/pilot80_dpd.npz; DEN=data/train/denver_full_dpd.npz
for b in $NEW; do
  [ -f data/raw/era5_g2_$b/DONE ] || { echo "missing data/raw/era5_g2_$b (docs/global/BUNDLE.md)" >&2; exit 1; }
done
for f in $NT $DEN configs/generator_global.toml; do [ -f "$f" ] || { echo "missing $f (docs/global/BUNDLE.md)" >&2; exit 1; }; done
$PY -c "from tempest.geo import holdout; holdout.places()" || exit 1
mkdir -p data/raw/empty_cds data/pilot data/train models/global

# (1) box datasets
FILES="$NT $DEN"
for b in $NEW; do
  P=data/pilot/profiles_g2_$b.zarr; D=data/train/g2_${b}_dpd.npz
  step heights_$b env TEMPEST_REGION=configs/region_g2_$b.toml $PY -W ignore -u -m tempest.profiles.to_heights \
    --raw data/raw/era5_g2_$b --cds data/raw/empty_cds --out $P --hours all --first-year 1991 --last-year 2025
  step build_$b env TEMPEST_REGION=configs/region_g2_$b.toml $PY -W ignore -u -m tempest.generator.build_dataset \
    --profiles $P --out $D --rows 3000000 --first-year 1991 --last-year 2025 --features base --rh-target dpd --fill-top --all-hours
  FILES="$FILES $D"
done

# (3) tropopause climatology (training years only) as an extra input column on every box file
if [ -f data/raw/era5_global/points.npz ]; then
  TAB=models/global/tropo_clim.npz
  step tropo_fit $PY -u -m tempest.geo.tropo_clim fit --out $TAB --last-year 2023
  F2=""
  for f in $FILES; do
    o=${f%.npz}_ztrop.npz; n=$(basename "${f%.npz}")
    step ztrop_$n $PY -u -m tempest.geo.tropo_clim overlay --data $f --table $TAB --out $o
    F2="$F2 $o"
  done
  FILES=$F2; ALL=data/train/g2_all_ztrop.npz
else
  log "no data/raw/era5_global: the tropopause column is skipped (G2 runs on the base columns)"; ALL=data/train/g2_all_dpd.npz
fi
# (2) join, row_group = position in FILES
step concat $PY scripts/concat_npz.py $ALL $FILES --group
set -- $FILES; BOXFILE=("$@"); BOXES=(nmtx denver $NEW)

# box edges for the IGRA shear check (from the region files)
REG=(configs/region.toml configs/region_denver.toml); for b in $NEW; do REG+=(configs/region_g2_$b.toml); done

cfg() {  # cfg CAND SEED -> config path: the candidate's generator config + balance_groups, seed set
  local c=$OUT/cand_$1.toml
  case $1 in
    global) cp configs/generator_global.toml "$c" ;;
    studt) { cat configs/generator_l3_studt.toml; echo; echo "balance_groups = true"; } > "$c" ;;
    siren) { cat configs/generator_l3_siren.toml; echo; echo "balance_groups = true"; } > "$c" ;;
    sirenstudt) { cat configs/generator_l3_studt.toml; echo; grep -E '^(geo_sh|geo_siren) ' configs/generator_l3_siren.toml; echo "balance_groups = true"; } > "$c" ;;
    *) cp "$1" "$c" ;;                                           # any other config path, used as given
  esac
  seeded "$c" "$2"
}

for S in $SEEDS; do
  for CAND in $CANDS; do
    C=$(cfg "$CAND" "$S") || exit 1
    T=$(basename "${CAND%.toml}")_s$S
    # pooled model: in-sample check against each box (G1-c rule)
    M=$OUT/pool_$T.pt
    step train_pool_$T $PY -u -m tempest.generator.train --data $ALL --out $M --max-year 2023 --min-year 1991 --config "$C"
    step calib_pool_$T $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $ALL --year 2023 --from-year 2021 --rows 60000 --m 199
    RUNS=$OUT/lobo_$T; mkdir -p "$RUNS"; echo "box,stem,lat0,lat1,lon0,lon1" > "$RUNS/lobo_runs.csv"
    for i in "${!BOXES[@]}"; do
      b=${BOXES[$i]}; L=$OUT/lobo_${b}_$T.pt
      cp -n $M "$OUT/pool_${b}_$T.pt" 2>/dev/null; cp -n ${M%.pt}.calib2021.npz "$OUT/pool_${b}_$T.calib2021.npz" 2>/dev/null
      step score_pool_${b}_$T $PY -W ignore -u -m tempest.scoring.score --model "$OUT/pool_${b}_$T.pt" --data ${BOXFILE[$i]} \
        --m 199 --first-test-year 2024 --last-test-year 2025 --calib "$OUT/pool_${b}_$T.calib2021.npz" --tail
      step train_lobo_${b}_$T $PY -u -m tempest.generator.train --data $ALL --out $L --max-year 2023 --min-year 1991 --config "$C" --exclude-group $i
      step calib_lobo_${b}_$T $PY -W ignore -u -m tempest.calibrate.spread --model $L --data $ALL --year 2023 --from-year 2021 --rows 60000 --m 199 --exclude-group $i
      step score_lobo_${b}_$T $PY -W ignore -u -m tempest.scoring.score --model $L --data ${BOXFILE[$i]} \
        --m 199 --first-test-year 2024 --last-test-year 2025 --calib ${L%.pt}.calib2021.npz --tail
      $PY -c "from tempest.region import load; r = load('${REG[$i]}'); print(f'$b,${L%.pt}_cal2021_fair,{r.lat_south},{r.lat_north},{r.lon_west},{r.lon_east}')" >> "$RUNS/lobo_runs.csv" || exit 1
    done
    step gate_$T $PY -W ignore -u -m tempest.scoring.spatial gate-g2 --dir "$RUNS"
    [ -n "${DRY:-}" ] || cp "$RUNS/gate_g2.csv" "$OUT/gate_g2_$T.csv"
  done
done
log "G2 finished for [$CANDS] seeds [$SEEDS]; return results/G2 as in docs/global/RESULTS_FORMAT.md"
