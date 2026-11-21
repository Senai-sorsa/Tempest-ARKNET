#!/bin/bash
# G5 packaging (docs/plans/GLOBAL_PLAN.md G5). Usage: scripts/global/g5.sh. Never G6 (scripts/final_test_global.sh, run once, not from here).
G=G5; . "$(dirname "$0")/g_common.sh"
not_built "a G4 global model (results/G4)" "ONNX FP16 / INT8 export of generator + corrector + statics/climatology tables" \
  "INT8-vs-FP32 gate (0.3 % CRPS, 1 % of the 99.9th shear) and the 250 ms / 75 MB checks"
