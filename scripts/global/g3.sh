#!/bin/bash
# G3 North-American continental lattice + global-style Mode F (docs/plans/GLOBAL_PLAN.md G3). Usage: scripts/global/g3.sh
G=G3; . "$(dirname "$0")/g_common.sh"
step store_check $PY scripts/g0_store_check.py
not_built "lattice point set (HEALPix nside=32, 15-75 N, 170-50 W + stratified mountain/coast + ~180 IGRA sites)" \
  "lattice dataset builder from data/raw/era5_global (int16 decode, RH clip, below-ground mask, holdout.check)" \
  "lead-time Mode F corrector with DeepSets summary over data/raw/wb2_hres_global" \
  "1,000 km block CV + seam test in tempest/scoring/spatial.py"
