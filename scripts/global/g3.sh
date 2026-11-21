#!/bin/bash
# G3 North-American continental lattice + global-style Mode F (docs/plans/GLOBAL_PLAN.md G3).
# Usage: scripts/global/g3.sh [CONFIG] [SEEDS]       default configs/generator_global.toml "0 100" (the seam test needs >= 2 seeds)
#   (1) lattice file from data/raw/era5_global: 15-75 N, 170-50 W, HEALPix nside 32 + all IGRA / terrain points,
#       30 % of the IGRA sites held out entirely; row_group = 1,000 km blocks (5 folds)
#   (2) eval files 2024-25: the held IGRA sites, the seen IGRA sites, two seam transects (36-44 N 125-75 W; 32-36 N 110-99 W)
#   (3) per seed: full model (train <= 2023, spread calibration 2021-23), scored on held and seen sites
#   (4) 1,000 km block CV (first seed): one model per left-out block fold, scored on that fold 2024-25
#   (5) seam test from all seeds; Mode F continental vs NM/TX-box corrector (only when data/raw/wb2_hres_global exists)
#   (6) gate: python -m tempest.scoring.spatial gate-g3 -> results/G3/gate_g3.csv
# Resume: rerun the same command; finished steps are skipped (results/G3/*.done).
G=G3; . "$(dirname "$0")/g_common.sh"
CFG=${1:-configs/generator_global.toml}; SEEDS=${2:-0 100}
[ -f data/raw/era5_global/points.npz ] || { echo "missing data/raw/era5_global (docs/global/BUNDLE.md)" >&2; exit 1; }
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }
$PY -c "from tempest.geo import holdout; holdout.places()" || exit 1
mkdir -p data/train models/global
step store_check $PY scripts/g0_store_check.py

TAB=models/global/tropo_clim.npz
[ -f $TAB ] || step tropo_fit $PY -u -m tempest.geo.tropo_clim fit --out $TAB --last-year 2023
BG="$PY -W ignore -u -m tempest.generator.build_global --rh-target dpd --statics --ztrop $TAB"
NA=data/train/g3_na.npz; NAB=data/train/g3_na_blocks.npz
step build_na $BG --out $NA --box 15 75 -170 -50 --nside 32 --hold-igra 0.3 --rows 4000000 --group point
step blocks $PY -u -m tempest.scoring.spatial regroup --data $NA --by block --size-km 1000 --k 5 --out $NAB
step build_held $BG --out data/train/g3_held.npz --points-from $NA --which held --first-year 2024 --rows 400000
step build_seen $BG --out data/train/g3_seen.npz --points-from $NA --which seen --first-year 2024 --rows 400000
step build_seam_w $BG --out data/train/g3_seam_w.npz --box 36 44 -125 -75 --first-year 2024 --rows 400000
step build_seam_nm $BG --out data/train/g3_seam_nm.npz --box 32 36 -110 -99 --first-year 2024 --rows 400000

score() {  # score MODEL DATA
  $PY -W ignore -u -m tempest.scoring.score --model "$1" --data "$2" --m 199 --first-test-year 2024 --last-test-year 2025 \
    --calib "${1%.pt}.calib2021.npz" --tail
}
fit() {  # fit MODEL CONFIG [--exclude-group N]
  local M=$1 C=$2; shift 2
  step train_$(basename "${M%.pt}") $PY -u -m tempest.generator.train --data $NAB --out "$M" --max-year 2023 --min-year 1991 --config "$C" "$@"
  step calib_$(basename "${M%.pt}") $PY -W ignore -u -m tempest.calibrate.spread --model "$M" --data $NAB --year 2023 --from-year 2021 --rows 60000 --m 199 "$@"
}

N=$(basename "${CFG%.toml}"); SEEN=(); UNSEEN=(); MODELS=(); BLOCKS=()
for S in $SEEDS; do
  C=$(seeded "$CFG" "$S") || exit 1
  M=$OUT/na_${N}_s$S.pt
  fit "$M" "$C"
  for w in held seen; do                                     # separate output names per eval set
    cp -n "$M" "$OUT/${w}_${N}_s$S.pt" 2>/dev/null; cp -n "${M%.pt}.calib2021.npz" "$OUT/${w}_${N}_s$S.calib2021.npz" 2>/dev/null
    step score_${w}_s$S score "$OUT/${w}_${N}_s$S.pt" data/train/g3_$w.npz
  done
  SEEN+=("$OUT/seen_${N}_s${S}_cal2021_fair"); UNSEEN+=("$OUT/held_${N}_s${S}_cal2021_fair"); MODELS+=("$M")
done

S0=${SEEDS%% *}; C0=$(seeded "$CFG" "$S0") || exit 1
for f in 0 1 2 3 4; do
  M=$OUT/blk${f}_${N}_s$S0.pt
  fit "$M" "$C0" --exclude-group $f
  step fold_$f $PY -u -m tempest.scoring.spatial subset --data $NAB --group $f --out data/train/g3_fold$f.npz
  step score_blk$f score "$M" data/train/g3_fold$f.npz
  BLOCKS+=("${M%.pt}_cal2021_fair")
done

for t in w nm; do
  step seam_$t $PY -W ignore -u -m tempest.scoring.spatial seam --data data/train/g3_seam_$t.npz --models "${MODELS[@]}" --out $OUT/seam_$t.csv
done

MF=""
if [ -d data/raw/wb2_hres_global ]; then
  MFG="$PY -W ignore -u -m tempest.forecast.modeF_global"
  step mf_rows_na $MFG rows --out data/train/g3_mf_na.npz --box 15 75 -170 -50
  step mf_rows_nm $MFG rows --out data/train/g3_mf_nmtx.npz --box 31 37 -109 -101
  step mf_train_na $MFG train --rows data/train/g3_mf_na.npz --out $OUT/mf_na.pt
  step mf_train_nm $MFG train --rows data/train/g3_mf_nmtx.npz --out $OUT/mf_nmtx.pt
  step mf_score_na $MFG score --rows data/train/g3_mf_nmtx.npz --model $OUT/mf_na.pt --out $OUT/mf_na_at_nmtx.csv --box 31 37 -109 -101
  step mf_score_nm $MFG score --rows data/train/g3_mf_nmtx.npz --model $OUT/mf_nmtx.pt --out $OUT/mf_nmtx_at_nmtx.csv
  MF="--modef $OUT/mf_na_at_nmtx.csv $OUT/mf_nmtx_at_nmtx.csv"
else
  log "no data/raw/wb2_hres_global: Mode F skipped (the gate reports it MISSING)"; MF="--modef $OUT/none.csv $OUT/none.csv"
fi

# the gate reruns on every launch
[ -z "${DRY:-}" ] && [ -f "$OUT/gate.done" ] && mv "$OUT/gate.done" "$OUT/gate.done.old"
step gate $PY -W ignore -u -m tempest.scoring.spatial gate-g3 --seen "${SEEN[@]}" --unseen "${UNSEEN[@]}" --blocks "${BLOCKS[@]}" \
  --seam $OUT/seam_w.csv $OUT/seam_nm.csv $MF --out $OUT/gate_g3.csv
log "G3 finished for $N seeds [$SEEDS]; return results/G3 as in docs/global/RESULTS_FORMAT.md"
