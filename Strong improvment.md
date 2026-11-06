# Strong improvements

Filtered from `C:\Users\Senai\Downloads\tempest_arknet_ai_weather_models_comparison.md` and the Gemini audit, then checked against `docs/APPLIED_STATUS.md`, `docs/FUTURE_OPTIONS.md`, `docs/PLAN.md` (IL log), `docs/PHASE4_LOG.md` and `Code-Modifications/AUTOPILOT.md`.

**How to judge every item:** use the usual rule. Run `compare_headline.py` and then `compare_shape.py` against the seed spread (IL-92: skill15 spread 0.0006 on ERA5, 0.0013 on balloons). A gain smaller than the seed spread counts as no gain. Mode F items are scored at the 1/3/5/7 d skill (r1 = 0.690/0.537/0.347/0.196; ridge = 0.679/0.524/0.332/0.191).

**No-download constraint (user, 2026-11-05):** follow section 5 and the instructions in section 6. Items A, E and F (and part of C) stay here for later, if downloading is allowed again.

None of this has been started. It is a plan only, and it does not overlap the work the other session is running right now.

---

## 0. Already queued: do not duplicate

| Overview item | Already covered by | State |
|---|---|---|
| B8 RH-weighted loss | F-19 (`ap_f19b.sh`, NaN fix) | queued |
| Station seam blending | F-20 (`ap_f20b.sh`, redo) | queued |
| Interaction terms (ONI x QBO) | F-14 salvage, IL-97 | queued |
| S4 attention over heights | IL-8 (stopped at step 500, cheaper rerun deferred) | deferred |
| Mask tokens / input dropout | IL-9 | todo |
| A1 more HRES starts/leads | F-8a / IL-75 (needs a notebook rerun, in ASK_LATER) | todo, so promoted to P0 below |
| MinT reconciliation | PLAN S6 | planned |
| Conditional sampling | IL-33 / IL-31..42 | planned, so A4 below builds on it |

---

## 1. Priority order

| # | Item | Cost | Why first |
|---|---|---|---|
| P0 | **A. Refetch WB2 HRES with 00Z+12Z starts, every 1-2 days, leads 6-240 h** | CPU + network, about a day | Unlocks the diurnal cycle, the 8-10 d range and about 4-8x more mode F cases. Several items below depend on it. |
| P1 | **B. Online EWMA bias tracker** | hours, no retrain | Cheap and independent of everything else. |
| P1 | **C. Wire `nearterm/ensemble.py` + EMOS into the api** | 1-2 days | The code exists but nothing uses it. |
| P2 | **D. Richer mode F inputs (time window, dProg/dt, gradients)** | GPU hours | Needs A. |
| P2 | **E. Per-lead ridge/EMOS for 7-10 d (lead cascade)** | CPU | Needs A. Ridge already ties the net at 7 d. |
| P2 | **F. Multi-model first guess (GraphCast/Pangu from WB2)** | network + CPU | Uses the same fetch path as A. |
| P3 | **G. `observe()`: importance-weight samples on an observation** | 1-2 days | Builds on IL-33. |
| P3 | **H. Sample-derived lapse rate in `to_site`** | hours | Small and testable on balloons. |
| P3 | **I. Spread-conditioned width (B11)** | hours | Needs C. |
| P4 | **J. ConvToken generator (cheap IL-8 rerun)** | GPU 2-4 h | Only if IL-9 shows tokens matter. |
| P4 | **K. Haar/DCT vertical CRPS term (B7)** | GPU 1-2 h | Test only. |
| P4 | **L. Lagged-run ensemble from the logger (A5)** | CPU | Only once the logger has about 60+ days. |
| — | **M. Evaluation hygiene (new)** | CPU | Do this alongside everything above. |

---

## 2. Items

### A. Refetch WB2 HRES: full diurnal cycle and 10-day leads (P0)

- **What:** pull 00 and 12 UTC starts, every 1 day (or every 2 days if disk is short), at leads of 6, 12, …, 240 h. WB2 `hres` has 12-hourly starts and 6-hourly leads to 10 d for 2016 to 2023-01 (IL-6).
- **Why:**
  - The current `data/raw/wb2_hres` has only 00Z starts every 4 days at leads 24/72/120/168. So every valid time is 00 UTC, about 17:00 solar (F-8a). That is why `api.py:176-177` limits mode F to `FORECAST_LEAD = (0.75, 7.5)` and `FORECAST_SOLAR = (14, 20)`.
  - IL-73/77 shows mode F overfits on about 2,576 cases, so data is the limit.
- **How:**
  1. `tempest/ingest/wb2_fetch.py` already takes `--leads` and `--every-days`. Add an `--hours 0 12` option for the start hours. The `year()` signature currently assumes 00Z only.
  2. Write to a **new** folder, `data/raw/wb2_hres_v2`, so the current training set stays untouched.
  3. Check the size on one year first and keep under the 50 GB cap. Crop to the 13x29 box and the 13 levels at fetch time, as now.
  4. Retrain mode F with the lead as a continuous input (IL-79) and a solar-hour input.
  5. Widen `FORECAST_LEAD` and `FORECAST_SOLAR` only for the ranges where the new model beats climate on the rule.
- **Judge:** skill at 1/3/5/7 d against r1, plus new 0.5/1.5/2.5 d and 8/9/10 d rows. A PIT check by solar hour.
- **Risk:** IL-84. More test dates are also needed to judge PIT, and this gives them.

### B. Online EWMA bias tracker (A3, simplified) (P1)

- **What:** a per-height, per-variable running bias of the live first guess against what actually happened. It is subtracted before mode F or the range map runs.
- **Why the simple version:** no aligned history exists to train a "PastContextEncoder" (it was dropped, see section 3). An EWMA needs no training.
- **How:**
  1. New `tempest/nearterm/bias.py`. State per (site, variable, height band, lead bucket): `b ← (1-α)·b + α·(forecast − verify)`, with α ≈ 1/30 per day. Store it as a small JSON next to the logger output.
  2. Verify against ERA5T analysis (about 5 days late) where it exists, and against IGRA balloons where present.
  3. Apply it in `tempest_weather/api.py`, only when the bias has at least N = 20 updates and |b| is more than 2 standard errors. Otherwise apply nothing.
- **Judge:** a backtest on 2022 WB2 HRES (it overlaps IGRA): EWMA-corrected vs raw MAE/CRPS by lead.
- **Cost:** hours.

### C. Calibrated live ensemble path (P1)

- **What:** feed `nearterm/ensemble.py` (it already converts the live Open-Meteo ensembles) through `router.py` (modes P/P0/F/F2/M/C already exist, with cosine hand-over) into the api. Add an EMOS calibration step.
- **How:**
  1. EMOS per height band and lead: `μ = a + b·ens_mean`, `σ² = c + d·ens_var`, fitted by CRPS minimisation (closed-form Gaussian CRPS is in `tempest/scoring/crps_gauss`).
  2. Training data for 500/700/850 hPa: WB2 `ifs_ens` (50 members, 2016-2024; those 3 levels only). Interpolate the coefficients over height for the other levels, and label them as interpolated.
  3. Once the daily logger archive (from 2026-11-05) reaches about 90 days, refit on it for all levels.
  4. Then apply the Schaake shuffle and the shear map as for mode F (IL-82, IL-58).
- **Judge:** CRPS and coverage90 against mode F on the overlapping leads; take whichever wins per lead.
- **Risk:** EMOS from 3 levels is weak above 500 hPa. Keep mode F/C there until the logger has enough data.

### D. Richer mode F inputs (P2, needs A)

- **What:** add three cheap input groups in `tempest/forecast/cond_matrix`:
  1. A **±6 h window**: the first guess at valid −6 h / 0 / +6 h. A1's 6-hourly leads give this.
  2. **dProg/dt**: the current run minus the run 12 h earlier at the same valid time (A gives the 12Z starts). It measures forecast instability.
  3. **Horizontal gradients** across the 13x29 box (∂T/∂x, ∂T/∂y, ∂z/∂x at a few levels) for advection and thermal wind.
- **Why it is not IL-1 again:** IL-1 added *ERA5 tendency* inputs to mode P and was inside the noise. These are *forecast* features that tell the corrector how much to trust the first guess.
- **How:** add one input group at a time, with ridge first (cheap) to see whether it lowers the error at all, then the net. Keep width 128 / depth 2 and the same weight decay. Overfitting is the known failure (IL-77).
- **Judge:** the rule, per group. Drop any group that does not clear the seed spread.

### E. Lead cascade as per-lead ridge/EMOS for 7-10 d (S3, simplified) (P2)

- **What:** past about 5 d, use per-lead ridge (or EMOS) on the first guess plus climate, instead of the net.
- **Why:** ridge already ties the net at 7 d (0.191 vs 0.196). A cascade of nets is not needed where a linear model ties.
- **How:** `tempest/forecast/residual` already has the ridge path. Fit one per 6-12 h lead bucket from the A data, and blend into mode C with the `router.py` cosine weights where the skill reaches 0.

### F. Multi-model first guess (new, P2)

- **What:** WB2 also archives GraphCast, Pangu, FuXi and NeuralGCM forecasts. Use the multi-model mean and spread as extra mode F inputs, or as alternative first guesses.
- **How:** use the same fetch path as A, into `data/raw/wb2_<model>`, cropped the same way. Check the start/lead cover of each model (some use 6-hourly leads and some 12-hourly), and their years. Start with GraphCast only.
- **Judge:** mode F with HRES only vs HRES + GraphCast mean/spread.
- **Live gap:** the tool needs the same models live. Open-Meteo serves some AI models, but check which, and check pressure-level availability, before committing.

### G. `observe()`: condition samples on an observation (A4) (P3)

- **What:** the user gives a pad observation (surface wind and temperature, or a morning sounding). The api returns samples consistent with it.
- **How:** follow the IL-33 design:
  1. Draw a large pool (for example 5,000) from the normal path.
  2. Weight each member by a Gaussian kernel on (obs − member) at the observed heights, with the kernel width set to the obs error plus the representativeness error.
  3. Resample to the requested N. Report the effective sample size, and warn when it is under about 50 (M18).
- **Not EnKF first:** an ensemble Kalman update assumes linear Gaussian errors, and shear tails are neither. Importance weighting keeps the sample shape. Try an EnKF update only if the ESS is often too small.
- **Judge:** hold out one balloon level as "obs" and score the other levels on balloons.

### H. Sample-derived lapse rate in `to_site` (B9) (P3)

- **What:** F-22 shifts by a fixed `-0.0065·dz·exp(-z/1500)`. Use instead the member's own lowest-layer lapse rate, clipped to [-0.0098, +0.01] K/m.
- **How:** a one-line change of the constant into a per-member value computed from the two lowest heights, in the same `to_site` function.
- **Judge:** on balloons only, at sites with |dz| > 200 m. Keep the constant if there is no gain (inversions can make the local lapse rate worse).

### I. Spread-conditioned width (B11) (P3, needs C)

- **What:** when the live ensemble spread is large, widen the mode F/range-map spread, and narrow it when the spread is small.
- **How:** an extra scale `s = clip((ens_sd / clim_ens_sd)^β, 0.7, 1.5)`, with β fitted by CRPS on the WB2 `ifs_ens` overlap, applied to the range-map deviation.
- **Judge:** coverage90 split by spread tercile. It should be flat across terciles after the change.

### J. ConvToken generator: the cheaper IL-8 rerun (S4) (P4)

- **What:** IL-8 attention over 44 tokens cost 1,700 s per 500 steps. Replace it with a 1-D conv stem (kernel 3-5 over height) that pools to 11 tokens, then attention, then unpools.
- **When:** only after IL-9 says token-style inputs help the shear tail.
- **Note:** the overview's "5.6 h → 14 min" number is unproven. Time 500 steps first.

### K. Haar/DCT vertical CRPS term (B7) (P4, test only)

- **What:** add a small extra afCRPS on the Haar (or DCT) coefficients of each profile, so that vertical structure at coarse scales is scored directly.
- **How:** a fixed orthonormal matrix applied to the target and the members in `tempest/generator/afcrps` callers; weight 0.1-0.3.
- **Caution:** EOF/B-spline bases and vertical conv sit in FUTURE_OPTIONS as "mediocre". This is a *loss* term, not a basis change, so it is cheap to test once. Drop it on any vertical-correlation regression (as with F-15).

### L. Lagged-run ensemble (A5) (P4)

- **What:** combine the last 2-4 logged runs (time-lagged) as extra members, weighted by age.
- **When:** only when the logger has enough history to fit the age weights (about 60+ days). Before that it is guesswork.

### M. Evaluation hygiene (new, alongside everything)

1. **A locked final test block.** Take one year (for example 2022 in WB2 / ERA5) out now and never use it for selection. FUTURE_OPTIONS already asks for this; it matters more as the number of candidates grows.
2. **Year-block cross-validation** for mode F instead of one split, so that a gain has to hold in most folds.
3. **A date-block bootstrap of the rule** (IL-87). Block by about 5 days so that autocorrelated days do not count as independent.
4. **Analog ensemble baseline (new).** For each forecast, find the K most similar past first guesses in the WB2 archive and use their verifying ERA5 profiles. It is a strong, untrained baseline that any learned mode F must beat. About 50 lines with NumPy nearest-neighbour on standardised features.

---

## 3. Filtered out, and why

| Recommendation | Verdict | Evidence |
|---|---|---|
| B12 slanted balloon-drift extraction | already tested, worse | F-10: T 5-12 km +9.2 % worse |
| B10 antithetic / extra members at training | already tested, discarded | F-15: no gain, worse vertical correlation. Sobol at inference stays in FUTURE_OPTIONS |
| Raise shear-tail loss weights | already tested, fails | IL-54..57. The shear map (IL-58/91/96) is the working route |
| Multi-stride loss | already tested, no gain | PLAN 2.4 |
| ERA5 tendency inputs for mode P | already tested, inside the noise | IL-1. Forecast-side features in D are different |
| PIT recalibration for mode F | already tested, no gain | IL-85 |
| Long-window shift / rare shear patches | already tested | IL-66 discarded, IL-5 not adopted |
| afCRPS α = 0.99 | already tested, no gain | FUTURE_OPTIONS |
| "PastContextEncoder" trained on 72 h of IGRA/ASOS innovations | will not work as stated | There is no aligned archive of the *live* first guess vs obs to train on. Replaced by the EWMA tracker (B) |
| Full 44-height ensemble calibration from WB2 `ifs_ens` | limited | `ifs_ens` has 500/700/850 hPa only. C uses it there and the logger elsewhere |
| Train on the AIFS / WN2 live 15 d ensembles | no history yet | Open-Meteo Ensemble is live-only; the logger began 2026-11-05. WN2 does have an Earth Engine/BigQuery archive (research-notes l.97-100), but check its levels and terms before planning on it |
| Mode M from EC46 | mostly unsupported | EC46 via Open-Meteo is surface-only; the persistence correlation in HANDOVER is small |
| Open-Meteo pressure-level lead history | does not exist | Phase 4 probe: Previous Runs is surface-only |
| GEFS reforecast | too large | over the 50 GB cap |
| The "30-60 % RMSE", "5.6 h → 14 min" style numbers | unsourced | judge everything with the rule instead |

---

## 4. Order of work, one line each

1. A (refetch into a new folder) → retrain mode F with lead + solar inputs → widen the api windows where it wins.
2. B and C in parallel (CPU, no GPU contention with the queue).
3. D, E and F on the A data, one input group at a time, ridge first.
4. G, H and I.
5. J, K and L only if their preconditions are met.
6. M throughout. Set up the locked test block **before** step 1 selects anything.

---

## 5. No-download plan (the one to follow now)

**Rule from the user:** download nothing beyond what is already downloading. That removes A, E, F and the WB2 `ifs_ens` part of C. It also removes parts 1-2 of D, which need A.

**Data on disk (checked 2026-11-05, `data/raw`, about 65 GB, already over the 50 GB cap):**

| Folder | Size | State |
|---|---|---|
| `era5_em` | 30 GB | done |
| `era5_em80` | 32 GB | done |
| `era5_em_denver` | 1.3 GB | done |
| `era5_cds` | 1.5 GB | **still downloading** (monthly GRIB from CDS; 61 months 1991-01..1996-01 on 2026-11-05, newest 199601). Do not read it as complete, and do not delete or move it |
| `igra`, `igra_denver` | 279 MB, 118 MB | done |
| `asos` | 20 MB | done |
| `wb2_hres` | 256 MB | done (00Z starts, every 4 d, leads 24/72/120/168 h) |
| logger archive | small | grows daily from 2026-11-05 (already running) |

**Does any idea make it vastly more accurate close in?** Only one: **G**, conditioning on a pad observation. A real measurement at the site beats any model for 0-12 h below about 3 km. The gain fades with height and lead time. Everything else is worth a few percent at best. Mode F stays limited to 0.75-7.5 d and 14-20 h solar time without A, so close-in mornings stay on climate modes. G is what fills that gap.

| Order | Item | Data used | Expected close-in gain |
|---|---|---|---|
| 1 | M. Locked test year + year-block CV + date-block bootstrap + analog baseline | `wb2_hres`, `era5_em*`, `igra` | none directly; stops fake gains being adopted |
| 2 | G. `observe()` importance weighting | the user-given obs; backtested on `igra` (hold out one level) and `asos` | **potentially large**, 0-12 h, low levels |
| 3 | B. EWMA bias tracker | backtest on `wb2_hres` vs `igra`/`asos` (2016-2022 overlap) | small to moderate (steady site/terrain bias) |
| 4 | H. Sample-derived lapse rate in `to_site` | `igra` sites with \|dz\| > 200 m | small; may lose during inversions |
| 5 | D part 3. Horizontal gradients from the 13x29 box | `wb2_hres` (already the full box) | small (shear via thermal wind) |
| later | C + I. EMOS on the live ensemble, spread-scaled width | logger archive only, after about 60-90 days | moderate, but not before then |
| later | J, K, L | as in section 2 | only once their preconditions are met |

---

## 6. Instructions for the session that does this work

Paste this section into a new Claude session (or give it to the current one once its queue is empty).

**Ground rules**
- Another Claude session may be training. Check first: `tasklist | grep python`. One process at about 2 GB is the trainer. Do not kill python processes you did not start (see memory `taskstop-orphans`).
- Do not touch `scripts/f20_seam.py`, `ap_f19b.sh`, `ap_f20b.sh` or the IL-97 run. They belong to the queue.
- **No new downloads.** Do not run `wb2_fetch.py`, CDS, or Open-Meteo history pulls. `era5_cds` is still downloading: leave it alone and treat it as incomplete.
- Thermal limits: at most 12 CPU threads and low priority (memory `thermal-limits`). GPU work only when the queue's GPU job is done.
- Every change goes behind a new config flag, default off, so current results are unchanged ("Dont break anything"). Log each item as a new IL row in `docs/PLAN.md` and its outcome in `docs/APPLIED_STATUS.md`.
- Judge with `compare_headline.py` then `compare_shape.py` against the seed spread (IL-92). Adopt only what clears it on the locked test year.

**Step 1: M, evaluation hygiene (CPU, about half a day)**
1. Pick the locked test year (2022 suggested; it is in `wb2_hres`, ERA5 and IGRA). Write it into `docs/PLAN.md` as "never used for selection". Add an exclusion check in the split code (`tempest/generator/split`, and the mode F loader `tempest/forecast/load_pairs`) that raises if that year is in train or validation.
2. Add year-block CV for mode F (leave one year out over 2016-2021). Report the mean and the number of folds won.
3. Add the date-block bootstrap (5-day blocks) to the rule output (IL-87).
4. Analog baseline: new `scripts/analog_baseline.py`. Standardise the `wb2_hres` first-guess features, find the K = 20 nearest past cases (same lead, ±45 days of season, other years only), and use their verifying ERA5 profiles as members. Score with `tempest/scoring/crps_ensemble`. Mode F must beat this.

**Step 2: G, `observe()` (CPU, 1-2 days)**
1. New function `observe(samples, obs, obs_heights, obs_sigma)` in `tempest_weather/` (next to `api.py`). Draw a pool of 5,000. Compute weights `w ∝ exp(-0.5·Σ((obs - member)/σ)²)`, with σ² = instrument error² + representativeness error² (start with 1 K, 1.5 m/s). Resample N with systematic resampling. Return the ESS, and warn when the ESS is under 50.
2. Accepted inputs: surface T/wind (from ASOS or the user), or a full morning sounding (IGRA format).
3. Expose it in `api.py` as an optional argument, defaulting to None (unchanged behaviour).
4. Backtest: for IGRA soundings, use the lowest 1-3 levels as "obs" and score the levels above on the same sounding; for 0-12 h, use the 00Z obs to score the 12Z sounding. Compare against no conditioning. Use a self-check test with a synthetic case where the truth is known.

**Step 3: B, EWMA bias (CPU, hours)**
1. New `tempest/nearterm/bias.py` with state keyed by (site, variable, height band, lead bucket); α = 1/30 per day; JSON state file next to the logger output.
2. Apply only when there are at least 20 updates and |b| is more than 2 SE.
3. Backtest on `wb2_hres` vs IGRA/ASOS in date order (no look-ahead), on 2016-2021. Confirm on the locked year only at the end.

**Step 4: H, lapse rate (CPU, hours)**
1. In the F-22 `to_site` code, replace the constant 0.0065 with the per-member lapse rate from the two lowest heights, clipped to [-0.0098, +0.01] K/m, behind a flag.
2. Score on IGRA sites with |dz| > 200 m only. Keep the constant if there is no gain.

**Step 5: D part 3, horizontal gradients (CPU ridge first, then GPU)**
1. In `tempest/forecast/cond_matrix`, add centred differences of T and geopotential across the 13x29 box at 850/500/250 hPa from `wb2_hres` (∂/∂x, ∂/∂y, about 12 features), behind a flag.
2. Ridge first. Go to the net (width 128, depth 2, same weight decay) only if ridge improves.

**Later (when the logger has about 60-90 days):** C (EMOS on `nearterm/ensemble.py` through `router.py`), then I (spread-scaled width). See section 2.

**When done:** update this file's section 0 table with the outcome of each item, and add one line per item to `docs/APPLIED_STATUS.md`.
