#!/bin/bash
# G4 global model (docs/plans/GLOBAL_PLAN.md G4).
# Usage: scripts/global/g4.sh [CONFIG] [SEEDS]       default configs/generator_global.toml "0"
#   (1) tables (training years only): Koppen groups, 2 deg climatology anchor (G5 bundle size), tropopause climatology
#   (2) global file from data/raw/era5_global (all store points, row_group = Koppen group 0-4) and three regrouped
#       copies: continent (leave-continent-out), 1,000 km blocks (5 folds), kNNDM (10 folds)   ~4 x 3.5 GB disk
#   (3) per seed: pooled model (train <= 2023, spread calibration 2021-23) + rotate-longitude check (first seed)
#   (4) first seed: one model per left-out Koppen group, continent, block and kNNDM fold, scored on that fold 2024-25
#   (5) area-of-applicability table, global balloon correction (pairs / fit / cv), EGPD shear tail (fit / check)
#   (6) gate: python -m tempest.scoring.spatial gate-g4 --dir results/G4 -> results/G4/gate_g4.csv
# Resume: rerun the same command; finished steps are skipped (results/G4/*.done).
G=G4; . "$(dirname "$0")/g_common.sh"
CFG=${1:-configs/generator_global.toml}; SEEDS=${2:-0}
[ -f data/raw/era5_global/points.npz ] || { echo "missing data/raw/era5_global (docs/global/BUNDLE.md)" >&2; exit 1; }
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }
$PY -c "from tempest.geo import holdout; holdout.places()" || exit 1
mkdir -p data/train models/global
step store_check $PY scripts/g0_store_check.py

# (1) tables
TAB=models/global/tropo_clim.npz; KOP=models/global/koppen.npz
[ -f $TAB ] || step tropo_fit $PY -u -m tempest.geo.tropo_clim fit --out $TAB --last-year 2023
step koppen $PY -u -m tempest.geo.koppen fit --out $KOP --last-year 2023
step clim $PY -u -m tempest.geo.clim_global fit --out models/global/clim_2deg.npz --last-year 2023 --res 2

# (2) data
GL=data/train/g4_global.npz
step build $PY -W ignore -u -m tempest.generator.build_global --out $GL --nside 0 --rows 4000000 --rh-target dpd --statics \
  --ztrop $TAB --group koppen --koppen $KOP
RG="$PY -u -m tempest.scoring.spatial regroup --data $GL"
step regroup_continent $RG --by continent --out data/train/g4_continent.npz
step regroup_block $RG --by block --size-km 1000 --k 5 --out data/train/g4_block.npz
step regroup_knndm $RG --by knndm --k 10 --out data/train/g4_knndm.npz

score() {  # score MODEL DATA
  $PY -W ignore -u -m tempest.scoring.score --model "$1" --data "$2" --m 199 --first-test-year 2024 --last-test-year 2025 \
    --calib "${1%.pt}.calib2021.npz" --tail
}
fit() {  # fit MODEL DATA CONFIG [--exclude-group N]
  local M=$1 D=$2 C=$3; shift 3
  step train_$(basename "${M%.pt}") $PY -u -m tempest.generator.train --data "$D" --out "$M" --max-year 2023 --min-year 1991 --config "$C" "$@"
  step calib_$(basename "${M%.pt}") $PY -W ignore -u -m tempest.calibrate.spread --model "$M" --data "$D" --year 2023 --from-year 2021 --rows 60000 --m 199 "$@"
}
groups() {  # groups FILE FALLBACK -> the row_group ids present in FILE (FALLBACK in a dry run, before the file exists)
  [ -f "$1" ] && $PY -c "import numpy as np, sys; print(*np.unique(np.load(sys.argv[1], mmap_mode='r')['row_group']))" "$1" || echo "$2"
}

N=$(basename "${CFG%.toml}")
for S in $SEEDS; do
  C=$(seeded "$CFG" "$S") || exit 1
  M=$OUT/pool_${N}_s$S.pt
  fit "$M" $GL "$C"
done

# (4) held-out folds, first seed
S0=${SEEDS%% *}; C0=$(seeded "$CFG" "$S0") || exit 1
cv() {  # cv KIND FILE IDS CSV LABELPREFIX
  local K=$1 D=$2 IDS=$3 CSV=$4 f M
  [ -n "${DRY:-}" ] || echo "fold,stem" > "$OUT/$CSV"
  for f in $IDS; do
    M=$OUT/${K}${f}_${N}_s$S0.pt
    fit "$M" "$D" "$C0" --exclude-group $f
    step fold_${K}$f $PY -u -m tempest.scoring.spatial subset --data "$D" --group $f --out data/train/g4_${K}_fold$f.npz
    step score_${K}$f score "$M" data/train/g4_${K}_fold$f.npz
    [ -n "${DRY:-}" ] || echo "$5$f,${M%.pt}_cal2021_fair" >> "$OUT/$CSV"
  done
}
cv koppen $GL "$(groups $GL '0 1 2 3 4')" loco_runs.csv koppen
cv cont data/train/g4_continent.npz "$(groups data/train/g4_continent.npz '0 1 2 3 4 5 6 7')" continent_runs.csv continent
[ -n "${DRY:-}" ] || tail -n +2 "$OUT/continent_runs.csv" >> "$OUT/loco_runs.csv"      # gate-g4: Koppen + continent folds together
cv block data/train/g4_block.npz "0 1 2 3 4" block_runs.csv block
cv knndm data/train/g4_knndm.npz "0 1 2 3 4 5 6 7 8 9" knndm_runs.csv knndm

# (5) checks and tables
P0=$OUT/pool_${N}_s$S0.pt
step rotate $PY -W ignore -u -m tempest.scoring.spatial rotate --data $GL --model $P0 --out $OUT/rotate.txt
step aoa $PY -W ignore -u -m tempest.scoring.spatial aoa --data $GL --out models/global/aoa.npz
BP=data/train/balloon_pairs.npz
step balloon_pairs $PY -W ignore -u -m tempest.calibrate.balloon_cov pairs --out $BP --first-year 1991 --last-year 2025
step balloon_fit $PY -W ignore -u -m tempest.calibrate.balloon_cov fit --pairs $BP --out models/global/balloon_cov.npz
step balloon_cv $PY -W ignore -u -m tempest.calibrate.balloon_cov cv --pairs $BP --out $OUT/balloon_cov_cv.csv
step egpd_fit $PY -W ignore -u -m tempest.calibrate.egpd fit --pairs $BP --out models/global/egpd.npz
step egpd_check $PY -W ignore -u -m tempest.calibrate.egpd check --pairs $BP --out $OUT/egpd_check.csv

# (6) gate (reruns on every launch)
[ -z "${DRY:-}" ] && [ -f "$OUT/gate.done" ] && mv "$OUT/gate.done" "$OUT/gate.done.old"
step gate $PY -W ignore -u -m tempest.scoring.spatial gate-g4 --dir $OUT
log "G4 finished for $N seeds [$SEEDS]; G5 packs $P0; return results/G4 as in docs/global/RESULTS_FORMAT.md"
