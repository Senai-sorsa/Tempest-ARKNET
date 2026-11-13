# New_Plan 15.4: old verdicts re-read after AU-1 and AU-4 (2026-11-13)

How the verdicts were found: `scripts/au15_4_scan.py` lists every "[lo, hi]" interval in New_Plan section 9,
docs/logs/LOOP3.md and docs/logs/AUTOPILOT.md. An interval is flagged when it excludes 0 and its nearer edge is
less than one interval width from 0 (the AU-4 criterion). It found 62 intervals; 25 were flagged, covering 14
verdicts. The rest were read by hand from the 15.4 table.

## Why most verdicts cannot change

- **AU-1** (thin clim15 pool, R median 75) only flattered skill against climatology: -0.013 skill15 on ERA5
  and -0.003 on balloons. A difference between two models scored on the same rows keeps its sign, because the
  bonus cancels.
- **AU-4** (one-day bootstrap blocks; 21-day blocks are now the default) only widens intervals. The median width
  grows x1.3-1.65, and up to x2.0-2.6 for u 5-12 km and T 12-18 km.

So no FAIL, KILL, MISS or CLOSED verdict can turn into a pass: a wider interval only makes "interval excludes 0"
harder, and rules based on point estimates do not use the interval at all. Only PASS, KEEP, CONFIRMED and MET
verdicts with a flagged interval are re-read below.

A rough test is used throughout: with the half-width hw, the interval still excludes 0 at width factor k when
|mean| / hw > k.

## Model vs model, interval near zero

| Verdict | Interval (1-day blocks) | abs(mean) / hw | Re-read |
|---|---|---|---|
| IL-207b per-site factor, CONFIRMED (seed 0) | TCS -0.079 [-0.116, -0.042] | 2.1 | holds at x1.65 |
| IL-207b replicate (seed 1) | TCS -0.075 [-0.140, -0.009] | 1.15 | **interval to confirm**: crosses 0 above x1.15. The CONFIRMED label rests on both seeds, so it becomes "seed 0 holds, seed 1 to confirm". Not adopted anyway (ASK_LATER 24); recompute with `kit_common.block_boot` on week labels before any adoption. |
| A1 step 2, MET (MAF tool + observe worse than persistence) | +0.037 [+0.007, +0.067] | 1.23 | **interval to confirm**: crosses 0 above x1.23. The persistence-law option it allowed was never built, so nothing to undo; recompute with multi-day blocks before building it. |
| IL-198 radar claim, 12-18 km band | +6.4 % [+2.7, +10.0] | 1.75 | holds at x1.65, but crosses at the x2.0-2.6 seen for T 12-18 km: **interval to confirm** for this band only. 2.5-5 km (5.0) and 5-12 km (2.6) hold. |
| C6 side note (FAIL stands) | CRPS -0.69 % [-1.19, -0.24] | 1.45 | the "CRPS did improve" side note is **to confirm**; the FAIL verdict does not change |

The other flagged intervals belong to verdicts that cannot flip:

- O4 FAIL, O1 FAIL, O3 FAIL, C6 FAIL.
- N2 MISS, N5 KILL, N6 KILL.
- G1-6 CLOSED.
- G1-3 (report only; balloon 0.14 [0.03, 0.26]; no change followed).

## "Beats climatology"

- **README and FINAL_REPORT ERA5 skill15**: AU-1 step 5 rescored the shipped stack once. The plain score was
  +0.030 to +0.032; the fair score is +0.017 to +0.021 (R 75, shift -0.013, the same in both seeds). The honest
  headline is about +1.7 to +1.8 % for an unknown site. Balloons: +0.017 -> +0.013 (known), +0.010 -> +0.007
  (unknown). Rewriting the README number is a wording change and waits until the fair baseline becomes the
  default (ASK_LATER 27, the user's call).
- **Tool trust lines**: they quote the same skill15 numbers, so the same note applies.
- **Mode F skill by lead, AV1 and AV2**: `scripts/il6_modeF.py` draws its climatology 199 times with replacement
  from all 2016-20 rows within 20 days and 250 m. That pool holds thousands of rows, not 75. Its bonus is
  therefore the plain m = 199 ensemble term, at most about 1/(2 x 199), roughly 0.25 % of the CRPS, which the
  model ensemble also carries. Against AV2's 7-22 % gain over climate at days 8-10 and Mode F's leads this is
  negligible. AV2 stays a MISS (it fails on cov99), and AV1 stays a KILL.

## Absolute skill thresholds

- **N1 PASS, "ERA5 skill15 >= 0.0287"**: the threshold is p2f 0.0277 + 0.001, so it is a model-vs-model
  difference. The AU-1 shift (-0.0133, reproducible to 0.0002) applies to both models and cancels. N1's gain
  (+0.0020 / +0.0026) is 4-5 x the seed noise, so the **PASS stands**. Its intervals were not part of the rule.
- No other section 9 rule uses an absolute skill-versus-climate threshold.

## Coverage, Earth-GRAM, 2026

- **Coverage rules** (RA stage 1a, G2-2, AV2's cov99, N1 coverage): unaffected by AU-1. Their point rules do
  not use the interval.
- **Earth-GRAM**: the comparison is model vs Gaussian, which AU-1 does not touch. The AU-7 wording applies when
  quoting it: +0.080 against a fixed-climate Gaussian, +0.074 against a recent-climate Gaussian.
- **2026 Jan-Jun final test**: not run, not touched. Caveat for when it is run: its climate skill must be
  scored with `--fair-baseline` (or read with the -0.013 note) and 21-day blocks. Whether to rerun anything is
  the user's call.

## Result

No verdict flips. Four items become "interval to confirm":

- IL-207b seed 1
- A1 step 2 MAF
- the IL-198 12-18 km band
- C6's CRPS side note

None of them changed the shipped tool. The README skill15 headline is overstated by about 0.013. This is
measured and recorded, and the wording waits for the fair-baseline default (ASK_LATER 27).
