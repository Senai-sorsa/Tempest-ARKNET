# Global stage (G1-G5) data bundle (New_Plan 28.6)

What to copy to the supercomputer. Sizes from `du -sh` on 2026-11-21. Time ranges were checked on the same day.
G6 (the one-time global final test) is NOT part of this bundle and must never be run from it.

## Code (always)
| Path | Size | Notes |
|---|---|---|
| `tempest/` | 11 MB | includes `tempest/geo` (holdout guard, statics, SH, clim, masks) |
| `scripts/`, `tests/`, `configs/` | 2.9 MB, 2.9 MB, 0.4 MB | `configs/global_holdout.toml` is the lock list |
| `pyproject.toml`, `docs/plans/GLOBAL_PLAN.md`, `docs/global/` | small | |
| `tempest_weather/` without `assets_final_2026h2/` | ~390 MB | the tool; only needed for G5 packaging parity |

## Data per stage
| Path | Size | Range | Needed by |
|---|---|---|---|
| `data/raw/era5_static/` | 23 MB | invariants + `derived.npz` | all |
| `data/raw/indices/` | 92 KB | to 2025 | all |
| `data/raw/era5_em/` (NM/TX) | 30 GB | 1990-10-29..2025-12-31 | G1-G4 |
| `data/raw/era5_em_denver_full/` | 6.4 GB | 1990-10-29..2025-12-31 | G1-G4 |
| `data/train/denver_full_*.npz` (pick the run's files) | 0.3-2.9 GB each | to 2025 | G1 |
| `data/raw/igra_denver_full/` | 118 MB | to 2022 | G1 |
| `data/raw/era5_g2_{vandenberg,canaveral,fairbanks,saltlake,lamont,hilo}/` | 5.2-5.3 GB each, 31.5 GB total | 1990-10-29..2025-12-31 | G2-G4 |
| `data/igra_heights/` (986 stations) | 4.1 GB | to 2025-12-31 | G2-G4 |
| `data/raw/igra_history/`, `igra_list/`, `igra_meta/` | 13 MB, 0.3 MB, 0.3 MB | metadata | G2-G4 |
| `data/raw/era5_global/` (7,483 points, int16) | 11 GB | 1991-01..2025-12 (checked: `docs/results/g0_store_check.txt`) | G3-G4 |
| `data/raw/era5_global_extra/` | 2.2 GB | to 2025 | G3-G4 |
| `data/raw/wb2_hres_global/` | 6.5 GB | to 2022-12 | G3-G4 Mode F |
| `data/raw/asos_global/` | 745 MB | to 2025 | G3-G4 near-surface |
| `models/av19_p2fden.pt`, `models/generator_80_p2f.*` | < 1 MB-tens of MB | | baselines B-raw (G1-G5) |

Total: G1 about 40 GB. G1-G4 about 95 GB. Send by stage if quota is tight.

## Never in the bundle (2026 = the locked final-test window)
- `data/raw/*2026*` (`asos_2026`, `era5_2026h2`, `era5_cds_2026h2`, `era5_em_2026h2`, `igra_2026`, `igra_denver_2026`, `indices_2026h2*`)
- `data/train/final_2026h2*`, `data/FINAL_TEST_2026H2_*`, `data/final_test_2026h2*.log`, `docs/final_test_2026h2/`, `tempest_weather/assets_final_2026h2/`
- **`data/raw/igra/*.zip` contains 2026 soundings.** Do not send it; G-stage code reads `data/igra_heights` (ends 2025).
- Anything at a locked holdout place (`configs/global_holdout.toml`). The global store already excludes them. Every G loader must still call `tempest.geo.holdout.check()`.

## Pack command (run from the repo root; review the list before sending)
No `*2026*` wildcard exclude: it would drop the station `BRM00082026`. The explicit list below already leaves out every 2026 folder and `data/raw/igra`.
```
tar -cf tempest_g_bundle.tar --exclude='__pycache__' \
  tempest scripts tests configs pyproject.toml docs/plans/GLOBAL_PLAN.md docs/global \
  data/raw/era5_static data/raw/indices data/raw/era5_em data/raw/era5_em_denver_full data/raw/igra_denver_full \
  data/raw/era5_g2_* data/igra_heights data/raw/igra_history data/raw/igra_list data/raw/igra_meta \
  data/raw/era5_global data/raw/era5_global_extra data/raw/wb2_hres_global data/raw/asos_global \
  models/av19_p2fden.pt models/generator_80_p2f.*
tar -tf tempest_g_bundle.tar | grep 2026   # expected: only data/igra_heights/BRM00082026.npz (a station id, not a date)
```
