# Global stage on the cluster (G1-G5)

Plan: `docs/plans/GLOBAL_PLAN.md`. Data to copy: `docs/global/BUNDLE.md`. What to send back: `docs/global/RESULTS_FORMAT.md`.
Copying the data and submitting jobs are done by hand (not automated). **G6, the one-time final global test, is never run from here.**

## Setup (once)
```
tar -xf tempest_g_bundle.tar && cd <bundle root>
sed -i 's/\r$//' scripts/global/*.sh scripts/*.sh && chmod +x scripts/global/*.sh   # packed on Windows: strip CRLF
uv sync && . .venv/bin/activate     # Python >= 3.12, pinned by uv.lock; torch 2.11 from the cu128 index (pyproject.toml).
                                     # If the cluster's CUDA driver is older than 12.8, install the matching torch wheel by hand.
python -m pytest tests/test_global_g0.py -q                          # 4 passed (statics needs data/raw/era5_static)
python scripts/g0_store_check.py                                     # prints OK and exits 0 (global store intact, no 2026, no holdouts)
```

## Run
Each launcher is one job. Rerun the same command after a crash or time limit: finished steps are skipped (`results/G*/NAME.done`).
`DRY=1 scripts/global/g1.sh` prints the commands without running them. `PY=/path/to/python` picks the interpreter.

| Job | Command | GPU / time (plan) | Status |
|---|---|---|---|
| G1 Denver test bed | `scripts/global/g1.sh [CONFIG] ["SEEDS"]`, e.g. `scripts/global/g1.sh configs/generator_p2f.toml "0 100"` | 1 GPU, ~2 × 4 trainings per config | runs: NM/TX train → calib 2021-23 → score NM/TX and Denver zero-shot 2024-25; unified NM/TX+Denver model scored at both |
| G2 eight boxes | `scripts/global/g2.sh ["CANDIDATES"] ["SEEDS"]` | 1 GPU, ~1 day | runs: per-box datasets, tropopause column, pooled + leave-one-box-out models, `gate_g2_<cand>_s<seed>.csv` |
| G3 NA lattice | `scripts/global/g3.sh [CONFIG] ["SEEDS"]` (default `configs/generator_global.toml "0 100"`) | 1 GPU, 1-2 days | runs: NA lattice (30 % IGRA held out), 2 seed models, 5 block-CV models, seam test, Mode F (if `data/raw/wb2_hres_global`), `gate_g3.csv` |
| G4 global | `scripts/global/g4.sh [CONFIG] ["SEEDS"]` (default seed 0) | 1-4 GPUs, 3-4 days | runs: Koppen / 2° climatology / tropopause tables, global file, pooled model, leave-Koppen-group / continent / block / kNNDM folds (28 models), rotate-longitude, AOA, balloon correction, EGPD, `gate_g4.csv` |
| G5 packaging | `scripts/global/g5.sh [MODEL]` (default the first `results/G4/pool_*.pt`) | 1 GPU or CPU, hours | runs: ONNX FP32 / INT8 (/ FP16) export + gates (`models/global/onnx/gates.json`), bundle `models/global/bundle` + `results/G5/bundle.csv` (< 75 MB) |

Exit codes: 0 done, 1 a step failed (see `results/G*/<step>.log`; fix, then rerun), 2 refused by a lock.
Order: G3 needs the G2 verdict only for the config choice; G4 after G3; G5 after G4. G5 needs `uv pip install onnx onnxruntime onnxconverter-common`.
Disk: G3 ~10 GB of training files, G4 ~4 x 3.5 GB (the global file and three regrouped copies). Memory: `--mem=64G` covers every step.
Gates rerun on every launch (cheap); every other finished step is skipped.
The CPU cap of the laptop (`scripts/cap_cpu.sh`) is not used here; set threads with the scheduler (e.g. `OMP_NUM_THREADS`).

Example Slurm wrapper (adjust partition and account):
```
#!/bin/bash
#SBATCH --gres=gpu:1 --cpus-per-task=16 --mem=64G --time=24:00:00
. .venv/bin/activate && PY=python scripts/global/g1.sh configs/generator_p2f.toml "0 100"
```
`--mem=64G`: the G1 concat step holds both training files in memory (about 9 GB on disk, more as arrays).

## Holdout rules (the locks)
- **Dates**: nothing on or after 2026-07-01 is read, trained on, tuned on or scored. The bundle holds no 2026 data at all. The launchers refuse to start if they find any (`data/raw/*2026*`, `data/train/final_2026h2*`, `data/raw/igra`, which holds 2026 soundings).
- **Places**: the 4 sites and 7 IGRA stations of `configs/global_holdout.toml` (1° radius) are never used. The global store already leaves them out. **Every new G-stage loader must call `tempest.geo.holdout.check(lat, lon, times)`**, which raises `HoldoutError`.
- `TEMPEST_FINAL_GLOBAL=1` unlocks both. It is for G6 only. The launchers refuse to run while it is set.
- No tuning on 2024-25: those years are the G1-G4 gate years (scored, never fitted). Training runs to 2023, calibration uses 2021-23.

## Data notes (G2-G4 code)
- Global store `data/raw/era5_global/YYYY-MM.npz`: int16 with the CODE scale/offset of `tempest.ingest.fetch_global`, 13 pressure levels, 7,483 points (`points.npz`).
- Decode, then **clip RH to 0-100 %**: the store holds -20.7 to 185.8 % (ERA5 supersaturation and interpolation). Mask pressure levels below ground with `tempest.geo.masks.below_ground(levels_hpa, sp_pa)`. The share below ground is 49 % at 1000 hPa and 12 % at 850 hPa.
- Static inputs: `tempest.geo.statics.statics(lat, lon)`. Spherical harmonics: `tempest.geo.sh.sh(lat, lon, L)`. Per-point climatology: `tempest.geo.clim.fit / predict` (refuses 2026).
