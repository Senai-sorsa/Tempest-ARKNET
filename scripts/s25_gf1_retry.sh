#!/bin/bash
# GF1 beside UR15: UR15 nest evals take the 12 GB GPU, so a GF1 training can die with CUDA out of memory. Rerun the (skip-finished) runner after a pause.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
export S25_PARALLEL=1
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  bash scripts/gpu_s25_gf1.sh && exit 0
  echo "$(date '+%F %T') [S25 retry] gf1 runner exited, attempt $i; pause 300 s" >> docs/results/logs/s25.log
  sleep 300
done
