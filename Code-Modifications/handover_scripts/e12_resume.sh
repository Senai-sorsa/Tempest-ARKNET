#!/bin/bash
# Wait for the orphaned E12 build (PID 35644) to exit, check its file, then resume e12.sh (which skips the build).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
while powershell -NoProfile -c "if (Get-Process -Id 35644 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"; do sleep 60; done
.venv/Scripts/python -c "import numpy as np; z=np.load('data/train/pilot80_smix.npz'); print('npz ok', z.files[:5])" || { rm -f data/train/pilot80_smix.npz; echo "partial build removed; rebuilding"; }
bash Code-Modifications/handover_scripts/e12.sh
