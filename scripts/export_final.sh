#!/bin/bash
# Group E: export the tool assets with every kept item. NOT run yet (the bundled assets stay as they are until the final model is chosen). Usage: bash scripts/export_final.sh [OUT]
# Kept so far: clean w head + its range map (IL-93), shuffle templates per 2 degree block + refit shear map (IL-95/IL-96), past-date surface pool (F-12), station-correction hybrid (F-11 part 1).
# Add --modep models/modeP_post.pt if F-11 part 2 is kept (and drop the plain models/modeP.pt); add --modef ... as in the current export (see tempest_weather/assets/manifest.json).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
OUT=${1:-tempest_weather/assets}
M=models/generator_80_p2f
PYTHONPATH=. .venv/Scripts/python -W ignore -m tempest.export_tool --model $M.pt --calib $M.calib2021.npz \
  --head models/whead_clean.pt --wcalib models/whead_clean.wcalib2021.npz --gust models/gust_model.npz \
  --post-templates data/train/pilot80_dpd.npz --post-cell 8 --post-smap $M.shearmap2021_cell8.npz \
  --modep models/modeP.pt --modep-sfc models/modeP_sfc_pool.npz --modep-sta models/station_map_mix.npz \
  "${@:2}" --out "$OUT"
