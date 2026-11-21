#!/bin/bash
# G1 Denver test bed (docs/plans/GLOBAL_PLAN.md G1) on the cluster: for one generator config and several seeds,
#   (1) train on NM/TX 1991-2023, range calibration 2021-23, score NM/TX 2024-25 and Denver zero-shot 2024-25 (G1-a, G1-b)
#   (2) train one unified model on NM/TX + Denver, score both (G1-c).
# Usage: scripts/global/g1.sh [CONFIG] [SEEDS]     default configs/generator_p2f.toml "0 100"
# Resume: rerun the same command; finished steps are skipped (results/G1/*.done).
G=G1; . "$(dirname "$0")/g_common.sh"
CFG=${1:-configs/generator_p2f.toml}; SEEDS=${2:-0 100}
NT=data/train/pilot80_dpd.npz; DEN=data/train/denver_full_dpd.npz; UNI=data/train/g1_nmtx_denver_dpd.npz
for f in "$CFG" $NT $DEN; do [ -f "$f" ] || { echo "missing $f (see docs/global/BUNDLE.md)" >&2; exit 1; }; done
$PY -c "from tempest.geo import holdout; holdout.places()" || exit 1          # lock list readable
N=$(basename "${CFG%.toml}")

score() {  # score MODEL CALIB DATA
  $PY -W ignore -u -m tempest.scoring.score --model "$1" --data "$3" --m 199 --first-test-year 2024 --last-test-year 2025 --calib "$2" --extras
}
fit() {  # fit TAG DATA CONFIG: train to 2023 + spread calibration 2021-23
  local M=$OUT/$1.pt
  step train_$1 $PY -u -m tempest.generator.train --data "$2" --out "$M" --max-year 2023 --min-year 1991 --config "$3"
  step calib_$1 $PY -W ignore -u -m tempest.calibrate.spread --model "$M" --data "$2" --year 2023 --from-year 2021 --rows 60000 --m 199
}

step concat $PY scripts/concat_npz.py $UNI $NT $DEN
for S in $SEEDS; do
  C=$(seeded "$CFG" "$S") || exit 1
  T=${N}_s$S
  fit nmtx_$T $NT "$C"
  M=$OUT/nmtx_$T.pt; K=${M%.pt}.calib2021.npz
  step score_nmtx_$T score "$M" "$K" $NT
  cp -n "$M" "$OUT/den0_$T.pt" 2>/dev/null                                   # zero-shot copy: separate output names
  step score_den0_$T score "$OUT/den0_$T.pt" "$K" $DEN
  fit uni_$T $UNI "$C"
  U=$OUT/uni_$T.pt; KU=${U%.pt}.calib2021.npz
  cp -n "$U" "$OUT/uni_den_$T.pt" 2>/dev/null
  step score_uni_nmtx_$T score "$U" "$KU" $NT
  step score_uni_den_$T score "$OUT/uni_den_$T.pt" "$KU" $DEN
done
log "G1 finished for $N seeds [$SEEDS]; return results/G1 as in docs/global/RESULTS_FORMAT.md"
