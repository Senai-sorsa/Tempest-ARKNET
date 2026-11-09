#!/bin/bash
# Group E: export the tool assets with every kept item. NOT run yet (the bundled assets stay as they are until the final model is chosen). Usage: bash scripts/export_final.sh [OUT]
# Kept so far: clean w head + its range map (IL-93), shuffle templates per 2 degree block + refit shear map (IL-95/IL-96), past-date surface pool (F-12), station-correction hybrid (F-11 part 1), lapse-rate map fitted on THIS model's stack (L21b, 2026-11-09: superadiabatic 0.338 -> 0.236, ERA5 0.219; T skill15 better in every band; parity test against tempest/calibrate/lapse_map.py).
# Add --modep models/modeP_post.pt if F-11 part 2 is kept (and drop the plain models/modeP.pt); mode F is included (modeF_v2).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
OUT=${1:-tempest_weather/assets}
M=models/generator_80_p2f
PYTHONPATH=. .venv/Scripts/python -W ignore -m tempest.export_tool --model $M.pt --calib $M.calib2021.npz \
  --head models/whead_clean.pt --wcalib models/whead_clean.wcalib2021.npz --gust models/gust_model.npz \
  --coherence models/coherence_lagcorr.npz --coherence-dist models/coherence_distcorr.npz --coherence-regimes models/coherence_regimes.npz --post-templates data/train/pilot80_dpd.npz --post-cell 8 --post-smap $M.shearmap2021_cell8.npz --post-lmap $M.lapsemap2021.npz \
  --modef models/modeF_v2.pt --modef-ridge --modep models/modeP.pt --modep-sfc models/modeP_sfc_pool.npz --modep-sta models/station_map_mix.npz \
  "${@:2}" --out "$OUT"
