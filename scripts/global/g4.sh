#!/bin/bash
# G4 global model (docs/plans/GLOBAL_PLAN.md G4). Usage: scripts/global/g4.sh
G=G4; . "$(dirname "$0")/g_common.sh"
step store_check $PY scripts/g0_store_check.py
not_built "global dataset builder from data/raw/era5_global (+ era5_global_extra, asos_global)" \
  "1 deg global climatology anchor with 12 EOFs (tempest/geo/clim.py is per point only)" \
  "Koppen class in tempest/geo/statics.py (needs a precipitation climatology)" \
  "global covariate balloon correction, pooled EGPD tail, DI/AOA flag" \
  "leave-one-climate/continent-out, kNNDM and rotate-longitude checks in tempest/scoring/spatial.py"
