# What passed, and where it is applied (2026-11-05)

"Applied" has three levels: **code default** (every user gets it), **flag** (exists, off by default, verified), **tool asset** (shipped to `tempest_weather`, used when the asset is exported). Nothing here is pushed.

| Item | Result | Where it stands |
|---|---|---|
| F-1, F-2, F-3, F-4, F-5, F-6, F-18, F-21, F-22, F-28 (review bug fixes) | fixed, tests | code default (tool and main package) |
| F-8 forecast mode in the tool | done, end-to-end tests | tool default for 0.75-7.5 days at 14-20 h solar |
| F-27 w-head range map | cov99 0.984 -> 0.990, CRPS equal | tool asset, **export flag** `--wcalib`; bundled assets not yet re-exported (done once at the end) |
| IL-91 / F-16 shuffle + whole-distribution shear map | vertical corr 0.08 -> 0.03, shear KS 0.044 -> 0.010, skill +0.0001, cov err 0.0034 -> 0.0031 | scorer flags; **tool**: code and export (`--post-templates --post-smap`) added 2026-11-05 with pooled templates, being verified (IL-94); bundled assets not yet re-exported |
| IL-11 seasonal widths (RH + surface) | ERA5 cov err 0.0034 -> 0.0025, balloons not scored | scorer flag; tool code path exists (`--post-seasonal`), not exported until the stack check (IL-16) passes |
| F-12 past-date surface spread (t2m, sp, rh2m) | CRPS t2m 1.16 -> 0.68 K, sp 48.8 -> 25.9 Pa, rh2m 3.75 -> 2.92 %, cov99 0.99-1.00 | tool asset `--modep-sfc`, not re-exported yet |
| F-13 ridge drivers | code done; scoring running | scorer flag |
| F-25, F-26 | no gain | discarded, flags off |
| F-7, F-7b split-window retrains | worse than p2f | discarded |
| IL-10, IL-12, IL-13, IL-3, IL-54..57 | discarded by the rule | flags off |

Not yet applied and why: F-10, F-11, F-12 (mode P retrain), F-14, F-15, F-19 (GPU retrains queued), F-17 (data), F-20/R-3 (dataset rebuild).

## How a candidate is judged (rule 4 plus the shape half, added 2026-11-05)
1. `compare_headline.py`: skill15, cov99 per variable x band, intervals (ERA5 and balloons).
2. `compare_shape.py` (via `shape_verdict.sh`): PIT distance, coverage error at all levels, skew, kurtosis, tail-rate error (ties counted half), event coverage gap, vertical correlation, shear KS. A metric is WORSE if it rises by more than the largest spread among three seeds of p2f (IL-92), floored at 2 %.
3. Real gain = skill15 up by more than the seed spread, or a shape metric better than the seed spread, and nothing worse in either test.
