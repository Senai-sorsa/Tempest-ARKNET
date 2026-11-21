#!/bin/bash
# G2 eight North-American boxes, leave-one-box-out (docs/plans/GLOBAL_PLAN.md G2). Usage: scripts/global/g2.sh
G=G2; . "$(dirname "$0")/g_common.sh"
for b in vandenberg canaveral fairbanks saltlake lamont hilo; do
  [ -f data/raw/era5_g2_$b/DONE ] || { echo "missing data/raw/era5_g2_$b (docs/global/BUNDLE.md)" >&2; exit 1; }
done
not_built "box dataset builder: data/raw/era5_g2_<box> zarr -> data/train/g2_<box>_dpd.npz (pilot builder generalised; must call tempest.geo.holdout.check, clip RH to 0-100 %, mask below ground with tempest.geo.masks)" \
  "climatological tropopause-height input column" "box-balanced sampler in tempest.generator.train" \
  "leave-one-box-out driver + scorer tempest/scoring/spatial.py (GLOBAL_PLAN section 6)" \
  "the G1 architecture choice configs/generator_global.toml (G1 output)"
