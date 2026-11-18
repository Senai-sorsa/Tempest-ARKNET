#!/bin/bash
# loop chain: paired base (seeds 0, 100), then GF4 (CPU), then GF1 (GPU). Restartable (arm steps skip finished outputs).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
for s in 0 100; do bash scripts/s25_arm.sh base $s configs/s25/base.toml || exit 2; done
bash scripts/cpu_s25_gf4.sh
bash scripts/gpu_s25_gf1.sh
