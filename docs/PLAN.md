# Tempest-ARKNET plan (v2)

Weather for **Monte Carlo flight simulation** at any place in the contiguous US, any day, 08:00–20:00
local time, from tomorrow to about three years ahead. Past dates are handled too.

Status (2026-11-05): the pilot-box system is built and scored (see the improvement log, the Phase 1-3 results and `docs/PHASE4_LOG.md` below); the original plan text that follows is kept as written.
The flight sim (FS / JARVIS, in the `dynamics` repo) is **not** changed by this work; its side comes later.

v2 rewrites v1 using the research report *Tempest-ARKNET Probabilistic Weather Architecture* (Nov 2026).
What was kept from it, what was cut, and why: [research-notes.md](research-notes.md).

## What changed from v1, in one paragraph

v1 produced a **mean and std per variable per height**. Sampling those independently gives a zig-zag wind
profile with fake shear, which is the one thing a launch dispersion study cannot tolerate (v1 pushed the fix
to phase 8). v2 makes **whole, physically coherent profiles** the product from day one: every Monte Carlo
draw is a real atmospheric column (an ERA5 profile from a similar day and hour, shifted to the target year),
or a real ensemble member for the next two weeks. Mean and std are still written, computed from the draws,
so the existing `dynamics` TOML keeps working. The neural surrogate goes from *first step* to an *optional
upgrade* that must beat this simpler engine on the backtest before it is built.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Monte Carlo distributions, mainly for future dates. Single-value sims of past/near-term dates can keep using `dynamics/tools/weather/Weather_to_JARVIS_inputs.py`. |
| Region | Contiguous US, 24–50° N, 125–66° W (box slightly over water for coastal sites). |
| Hours | 08:00–20:00 local. Stored on solar 06–21 h so every local hour in range is covered across time zones and DST. Queries outside 08–20 are refused. |
| Product | **N coherent profile samples** (default 1,024) + mean/std per variable and height, from the samples. |
| Variables | Profiles of wind east/north (u, v), temperature, relative humidity; surface temperature, pressure, RH, 10 m wind. Pressure and density at height follow from T and RH by the hypsometric equation. T and RH are kept: same data pull, and the sim's atmosphere is currently `StandardAtmosphere1976`, which a real T profile replaces later (a June afternoon at Spaceport America is ~15–25 °C warmer than standard at the surface between 08:00 and 20:00, so ~5–9 % lower density). |
| Vertical grid | Fixed heights **above ground**, not pressure levels (pressure levels lie under the ground over the West): 10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000 m, then every 500 m to **18 km** (44 levels). Why 18 km: Sol Invictus targets 45,000 ft = 13.7 km apogee and is flown to impact, so descent drift crosses every layer; 18 km leaves ~30 % margin for dispersed and future vehicles. ERA5's top usable levels are 100 hPa (~16 km) and 50 hPa (~20.5 km), so 18 km is inside the data for any CONUS site below ~2.5 km elevation; above that the top heights are clipped to the 50 hPa height. |
| Latency | One weather query per Monte Carlo **campaign**, not per run or per step: `dynamics`' monte-carlo mode writes one mean/std TOML that the sim samples from. Budget: site lookup ≤ 50 ms from the local store, drawing 1,024 samples < 1 ms. This removes any speed reason for a neural network. |
| Pilot | **Spaceport America** (32.99 N, 106.97 W, 1,400 m; the sim's current site, `sites/spaceport_america.toml`) and **Midland, TX** (31.94 N, 102.19 W, 875 m; IREC has been held there since 2025 and returns in 2027). Each has an active IGRA radiosonde nearby: Santa Teresa NM `USM00072364` (~125 km) and Midland `USM00072265` (on site). One small box (31–34 N, 108–101 W) covers both. |
| Season focus | Whole year is stored; acceptance is reported for all months *and* separately for June (IREC season), so a good June is not hidden by an average. |
| Engine | **Neural generator (option 3A, Engression)** for > 15 days, decided 2026-11-04; see *Engine decision*. The **trend-adjusted analog sampler** (below) is built first, as its baseline and fallback; the router picks whichever wins per lead band and region. |
| Long-range predictors | Linear trend in year, ENSO (ONI), and QBO for winds ≥ 10 km. Each term kept only if it passes the significance and backtest tests. No CMIP6 / LOCA2: scenarios do not diverge within 3 years, and LOCA2 has no upper-air winds. |
| Accuracy target | Replaces v1's "R² ≥ 0.999": see *Acceptance criteria*. Months to years ahead, no method predicts the weather itself; the target is an honest, calibrated distribution. "99.9 %" is defined in *Engine decision*: exact lookup for past dates, and 99.9 % bands that hold 99.9 % of radiosonde outcomes. |

## Settled questions (2026-11-03)

All v1/v2 open questions are decided above. Reasoning for the two not in the table:

- **Weeks 3–6 and months 2–7.** No extra source at first. Days 10–15 blend ensemble into analogs; beyond
  that, analogs with trend/ENSO/QBO. Real-time ECMWF extended range has service charges and the free S2S
  archive is delayed; the report's own skill estimate for these leads is small (CRPSS ≈ 0.01–0.15). The free
  C3S seasonal monthly means (CDS) are tried in phase 9 and kept only if they beat the phase 8 system.
- **QBO term.** Kept as a *candidate*, not assumed: the QBO is equatorial, and its signal at 32° N is weak,
  but QBO forecasts themselves hold a correlation > 0.7 at 12 months, so it is the one predictor that stays
  forecastable over the 1–3 year range. The backtest decides.

Nothing is left for the user to decide before phase 1.

## Architecture

The user-facing tool (portable `tempest_weather/` folder, `values()` and `distribution()`, four modes) is planned in
[TOOL_PLAN.md](TOOL_PLAN.md).

```
query (lat, lon, date, local time, N)
   │
   ├─ lookups: elevation, timezone → solar hour, ONI/QBO history + forecast
   │
   ├─ router by lead time
   │     past (in store) ........ ERA5 profile at that hour + launch-slip window + ERA5 error
   │     past (after store end) . Open-Meteo historical-forecast API (has pressure levels)
   │     0–15 days ............... pooled members: Google WeatherNext 2 (64) + ECMWF IFS ENS (51), via Open-Meteo,
   │                                each calibrated before pooling
   │     10–15 days .............. blend: ensemble members → analogs, weight by lead
   │     > 15 days ............... neural generator (3A) where it wins the backtest, else trend-adjusted analogs
   │
   ├─ calibration: spread inflation per (variable, height, lead band), from the backtest
   │
   └─ out: samples file (N × heights × vars) + TOML (mean/std, [wind_profile], source line)
```

### The analog sampler (the core)

For a target site, day and hour:

1. **Candidates.** All stored ERA5 profiles at the 4 surrounding 0.25° grid points within ±7 days of the
   target day-of-year and ±1 h solar time, in every stored year. With 1991–2025 that is about
   35 years × 15 days × 3 hours ≈ 1,500 real profiles per point.
2. **Spatial blend.** For each candidate timestamp, blend the 4 neighbours' profiles with bilinear weights.
   Same-time blending keeps the column coherent. Heights are above ground, so terrain is mostly handled.
   Surface T and pressure get a lapse-rate / hypsometric correction from ERA5's grid elevation to the site's.
3. **Shift to the target year.** For each candidate from year *y*:
   `x' = x + b·(Y − y) + c·(ONI_Y − ONI_y) + d·(QBO_Y − QBO_y)`, per variable and height.
   Coefficients b, c, d are fitted per region, season and height on the store, and set to zero unless |t| ≥ 2
   *and* they improve the walk-forward backtest. This is v1's Layer 2a/2b, applied to samples instead of
   to means.
4. **Predictor uncertainty.** For each draw, ONI_Y and QBO_Y are drawn from their forecast distributions
   (a lead-specific lagged regression with its residual spread, falling back to the target month's
   climatology once it has no skill: about 12–18 months for ONI once warm water volume is a predictor
   (about 6 months without it), and about 2 years for QBO; measured in
   [PHASE1.md](PHASE1.md) §5), and the trend term gets its extrapolation error. v1's four-part variance formula falls
   out of this automatically: within-season spread and year-to-year scatter are already in the analog set; trend
   and ENSO-forecast uncertainty come from the predictor draws.
5. **Draw** N samples with replacement. Mean/std are computed from them.

Why this rather than v1's surrogate network, or the report's FGN/EOF generator:
- Vertical shear, u–v correlation, T–wind (thermal-wind) balance and boundary-layer inversions are **real by
  construction**: nothing is modelled, so nothing can be modelled wrong.
- No training, no loss-weight tuning, no extrapolation risk. The only fitted parts are a few linear
  coefficients, each tested.
- It is the standard to beat anyway: a network that cannot beat resampled history is not worth shipping.

Known limits (each has a phase that checks it): ERA5 is smoother than reality, mostly for wind (phase 6
inflates against radiosondes). Sub-grid terrain at 0.25° is missed (heights above ground and the elevation
correction take most of it; spatial-block CV in phase 8 measures what is left). Distribution tails cannot
exceed what history plus the shift contains; ~1,500 analogs per point is enough for 99th percentiles but
thin for 99.9th.

### Near-term (0–15 days)

Verified 2026-11-03: Open-Meteo's ensemble API with `models=ecmwf_ifs025` returns **51 members** with
pressure-level wind for about 15 days (the GFS ensemble does not; the ERA5 archive endpoint does not).
Each member is a coherent profile: convert it to heights above ground with its geopotential, treat each member
as a sample, and add the per-variable analysis-error noise. Over days 10–15, mix members and analogs with a
weight that moves linearly from ensemble to analogs. One request per query; keep `dynamics`' retry with
backoff on HTTP 429 (free tier ≈ 10,000 calls a day, few concurrent).

**Multi-model pool (added 2026-11-04).** Open-Meteo also serves Google **WeatherNext 2**
(`models=google_weathernext2_ensemble`: 64 members, 0.25°, 6-hourly, 13 pressure levels, 15 days) and ECMWF
**AIFS ENS** (`ecmwf_aifs025_ensemble`, 51 members). Pool WeatherNext 2 and IFS ENS members. A blend helps only
when the models' errors differ, and these two come from different lineages: one is an AI model trained on CRPS,
the other is physics. AIFS ENS is trained on IFS analyses, so it adds little diversity; add it only if the
backtest says so. Apply spread inflation to each source on its own first, then fit one inflation for the pool
(arXiv 2610.42130). Pool weights are tuned on the verification archive below. Equal weight per member is the
default until then.

**Verification archive.** Open-Meteo keeps past ensemble members only since 2026-08-03. Its
historical-forecast API returns the member series, but every value is null. So:
(a) a small daily logger, started in phase 1, saves both models' members at the pilot sites;
(b) WeatherNext 2's own archive, with members, 2022-01 to now and CC-BY-4.0, on Earth Engine
(`projects/gcp-public-data-weathernext/assets/weathernext_2_0_0`; free for research and non-profit use) or
BigQuery, gives hindcasts for calibration.

### Past dates

Inside the store: the actual ERA5 profile at that hour, with spread from (a) the launch-slip window (profiles
at ±N h the same day) and (b) ERA5 analysis error (start with published values: ~1–2 °C, ~1 hPa, ~10 % RH,
~1.5–2.5 m/s per wind component; phase 6 replaces them with radiosonde-fitted values). After the store's end
date: Open-Meteo historical-forecast API, which has pressure levels (verified), with the same spread treatment.

## Optimal structure (v3, 2026-11-04)

Source: the Argon cross-domain report (*Cross-Domain Probabilistic Curve Prediction*), its top-ranked hybrid
SCAT-RCT, checked against the arXiv API and adapted to our variables. It is an **upgrade of the analog core,
not a replacement**. Every draw still starts as a real ERA5 profile, so the joint shape stays real. The
new stages fix the three known limits: ERA5 is too smooth, tails are capped by history, and calibration
can break the joint shape. Each stage is switched on only if it improves the walk-forward backtest, the
same rule as the shift terms.

```
query
 │
 S0 driver draws ......... ONI_Y, QBO_Y, trend error drawn by Latin hypercube (stratified), widening to
 │                         climatology as forecast skill runs out                       (P8, 2607.12730)
 S1 router by lead ....... 0–15 d: each provider calibrated alone (EMOS), then a linear pool of members with
 │                         weights shrunk toward equal (Stacked Gibbs, 2509.04203), then one
 │                         post-pool calibration (2610.42130); days 10–15 hand over to analogs
 S2 retrieve ............. analogs: ±7 d, ±1 h solar, per-year cap, optional kernel weight on driver
 │                         closeness                                            (P6, 2606.04135)
 S3 shift ................ x' = x + b·ΔY + c·ΔONI + d·ΔQBO, coefficients partially pooled across heights
 │                         and points                                                  (2606.23009)
 S4 station transfer ..... split each profile into surface value + 43 neighbour differences per variable;
 │                         quantile-map ERA5 → IGRA in difference space per (variable, height band,
 │                         season); beyond the 99th percentile a GPD tail with ξ shared per variable,
 │                         bounded to [-0.1, 0.25], only the scale varying                (P4, P5, 2606.30821)
 S5 rank reorder ......... put the transferred values back in the raw analogs' rank order per coordinate
 │                         (ECC), then sum the differences up from the surface          (P1, 2608.12998, 2609.25980)
 S6 reconcile ............ two estimates of each level exist: calibrated directly, and surface + summed
 │                         differences. Combine them with one fixed projection (MinT, Ledoit-Wolf-shrunk
 │                         error covariance, block per variable) so summing does not drift  (P9, 2608.13886)
 S7 calibrate ............ scale each draw's deviation from the sample mean per (variable, height band,
 │                         lead band) by an online conformal factor. The whole cloud is scaled, so the
 │                         joint shape is kept. Wind as a (u, v) vector; only matured verifications
 │                         (P10, 2608.17333, 2605.17250)
 out
```

Notes:
- **Why difference space only from S4 on.** A linear shift gives the same result in level space and
  difference space, so S3 stays as it is. Difference space matters for the non-linear steps (quantile map,
  GPD tail), because downstream the shear is what matters, and it is shear that ERA5 smooths.
- **Why distribution matching, not mean + noise.** Mean-plus-residual corrections come out biased and too
  narrow on real data (2606.30821). A quantile map matches the whole station distribution.
- **Speed.** S4–S7 are table lookups, a sort and one small matrix product. Check against the 1 ms budget for
  1,024 draws in phase 7. If S6 is over budget, apply it to the differences only.
- **Falsification test, run in phase 6.** Add only S4 + S5 + S6 to the phase 4 sampler. On 10 walk-forward
  years and 20 held-out IGRA stations, it must give ≥ 3 % better variogram score and ≥ 15 % lower error on the
  99.9th-percentile neighbour difference. Otherwise phase 6 falls back to plain inflation + conformal +
  GPD as written in the phase table.
- **Not taken (traps flagged by the report).** Multi-step diffusion on the 44-level profile, deep transformers,
  unconstrained GANs/VAEs, unregularized pool weights on a short archive, hard clamping of values, and
  conformal sampling of each height on its own. All of them either overfit 35 independent years or break
  the joint shape.

## Options by complexity

The optimal structure above is option **2A**. The others are ranked within each level by expected gain per
unit of effort. Every option is gated: it ships only if it beats what it replaces on the walk-forward
backtest.

### Level 1: simple (days, no training, low risk)

| # | Option | Fixes | Falsified if | Effort |
|---|---|---|---|---|
| 1A | **Current plan + rank reorder + difference-space GPD tails** (S4's tail and S5 only, no station quantile map) | 99.9th-percentile shear capped by history; calibration breaking the joint shape | 99.9th-percentile neighbour-difference error on IGRA not lower than plain inflation | 3–5 days |
| 1B | **Stratified driver draws + driver-kernel analog weights** (S0 + S2's kernel) | Noisy ONI/QBO/trend propagation at N = 1,024; analogs from years with the wrong ENSO state | CRPS at 6–24 months not better than random draws, beyond fold-to-fold noise | 2 days |
| 1C | **Partially pooled shift coefficients**, or OnlineLASSO pruning, instead of keep/drop per point | Coefficients flip on and off between neighbouring heights; 35 years is a small sample | Walk-forward CRPS not better than the \|t\| ≥ 2 rule | 3–4 days |
| 1D | **EMOS per provider → shrunk linear pool → post-pool calibration** for 0–15 days (S1) | Pool weights overfitting a short archive; providers with different biases | Pool not better than the best single provider on CRPS and energy score | 3 days |

### Level 2: medium (weeks, light fitting, no neural network)

| # | Option | Fixes | Falsified if | Effort |
|---|---|---|---|---|
| 2A | **Optimal structure** (S0–S7) | All three known limits at once, keeping real analogs | The phase 6 falsification test above | 2.5–3 weeks |
| 2B | **Spectral generator**: per variable, the profile's first ~12 DCT modes of the differences; a Gaussian whose mean and covariance depend on the drivers; a Fisher-orthogonal B-spline tilt for skew (DCDN, 2610.35137); a GPD tail layer | Only ~1,500 analogs per point; can produce profiles no year had | 12 modes lose > 5 % of the 99.9th-percentile neighbour-difference amplitude, or variogram score worse than analogs | 2–3 weeks |
| 2C | **Shear codebook**: residual-quantized codebooks (32/64/128 entries) of difference-space profiles, routed by drivers and season through a low-rank map, plus GPD tails | CONUS store size (phase 8) and lookup speed; smooths analog sampling noise | Variogram score more than 2 % worse than raw analogs | 2–3 weeks |

### Level 3: advanced (1–3 months, one GPU, highest risk)

| # | Option | Fixes | Falsified if | Effort |
|---|---|---|---|---|
| 3A | **Engression generator** in difference/DCT space: noise added before the network, trained on the energy score, drivers as inputs (Engression 2307.00835; DExtrI 2608.19849). Extrapolates beyond the trend range | Future years partly outside the training range; non-linear driver effects | Not better than the linear shifts at 1–3 years, or worse than resampled history at any lead | 4–6 weeks |
| 3B | **One-step flow generator** (shortcut model, 2410.12557) with a smooth along-height prior, conditioned on retrieved analogs, trained with energy + variogram loss and checked with a tail-sensitive metric (CSig-MMD, 2602.10182); pre-trained on an ACE2 emulator run if 35 years overfit | Smoothness and tails at once, with single-step sampling inside the 1 ms budget | Worse than resampled history at ≥ 1 year | 6–10 weeks |
| 3C | **Multi-fidelity station generator**: learn the ERA5 → radiosonde residual distribution conditioned on terrain and site (ReMatch 2606.30821; multi-fidelity SBI 2507.00514) | S4's quantile map exists only near the ~100 IGRA stations; this carries it to any CONUS point | On spatial-block CV, not better than the nearest-station quantile map | 4–6 weeks |
| 3D | **In-context foundation model for drivers → profile modes** (TabPFN-TS on 5 PCA modes, used off the shelf) | Driver-conditioned shifts at 6–24 months without hand-picked terms | Not better than the linear driver regression at 6–24 months. Quick, about 1 week, so run it first | 1 week test |

**Recommended order:** 1B and 1C inside phase 4; 1D in phase 5; 2A in phase 6 (1A is its fallback if
the falsification test fails); 3D as a cheap probe in phase 9; then 2B, 2C, 3B in phase 9 only if the
phase 8 system still falls short on tails, store size or unseen sites. **Update:** 3A was promoted to the
main engine (phase 6A), and 3C feeds it at CONUS scale (phase 8); see *Engine decision*.

## Engine decision (2026-11-04): neural generator 3A

Decided by the user: option **3A** becomes the main engine for dates more than 15 days ahead. The analog
sampler (phases 3–4) and the station correction (phase 6) are still built first. The generator needs them:
the analogs are its baseline and fallback, and the station correction is where its training targets come
from. The router uses the generator for each lead band and region **where it beats the analogs on the
backtest**, and analogs everywhere else. So both engines always exist, and either can answer a query.

### What it is

```
inputs  ─ place: lat, lon, site elevation, ERA5 grid elevation
        ─ time: sin/cos day of year, sin/cos solar hour
        ─ climate state: year (trend), ONI, WWV, QBO u30/u50   ← drawn per sample by S0
        ─ noise ε (16–32 numbers, Gaussian)                     ← added at the input ("pre-additive")
            │
            ▼
        4 residual blocks × 512 wide, about 2.9 M parameters per member  (tempest/generator/, configs/generator.toml)
            │
            ▼
outputs ─ per variable: surface value + 43 neighbour differences (u, v, T, RH), standardised
        ─ surface T (2 m), p, RH (2 m); 10 m wind = first profile height
            │
            ▼
        sum the differences up from the surface → 44-level profile
```

- **Why Engression** (arXiv 2307.00835): the noise goes in before the network, not after it. That lets the
  model extrapolate a little beyond its training range, which matters because 2027–2029 are warmer than
  every training year. DExtrI (2608.19849) is the follow-up for interactions between drivers.
- **Loss** (as ECMWF AIFS-CRPS): per-value almost-fair CRPS on the rebuilt, standardised profiles, plus
  0.1 x energy score on the whole vector to keep heights jointly consistent. Both are proper scores, so the
  model is rewarded for the right spread and joint shape, not just the right mean. 4 samples per row.
  The variogram score is used for evaluation (scorecard), not in the loss: from 4 samples it is too noisy.
- **Network:** residual blocks whose layer norms are shifted and scaled by an embedding of the noise vector
  (as AIFS-CRPS / DeepMind FGN): depth 4, width 512, noise 32; 2,881,074 parameters per member (E12 checkpoint). 4 independently trained seeds are pooled at sampling
  time (4x the training time below).
- **Training targets:** ERA5 profiles after the station correction. The generator learns balloon-like shear
  and spread, not ERA5's smoothness. Pilot: S4's quantile map (both sites have a nearby IGRA station).
  CONUS: **option 3C** (a learned ERA5 → radiosonde correction conditioned on terrain and site) carries
  the correction to points far from any station, and 3A is retrained on its output (decided 2026-11-04).
- **Training data:** pilot box first, then CONUS samples drawn from the store on the fly (phase 8).
  Measured 2026-11-04 on this machine's RTX 5070 Laptop GPU (12 GB) at pilot size (400k rows, 13 inputs,
  179 outputs): 17–30 ms per step at batch 4,096, 0.4 GB GPU memory, so a 20,000-step run takes about
  6–10 minutes. An RTX 4090 is faster. The CONUS limit will be disk and RAM, not the GPU.
- **Sampling:** draw N noise vectors and N driver sets, then run one forward pass for all of them. Measured:
  1,024 profiles in 1.4 ms on the GPU and 10 ms on the CPU, including the copy back. That misses the
  < 1 ms draw budget but fits easily inside the 50 ms per-query budget, and there is one query per
  Monte Carlo campaign, so it does not matter in practice.
- **After the generator:** extreme-value tails (S4's GPD), then whole-cloud conformal scaling (S7), the
  same as for analogs, so both engines share one calibration path.

### Distributions it returns

Every query returns N joint samples, so any summary comes from them: mean/std (the `dynamics` TOML),
quantiles 0.1 %…99.9 % per variable and height, exceedance probabilities (e.g. P(shear 1–2 km > 10 m/s)),
and the samples file. For past dates, the same outputs describe the uncertainty around the ERA5 value.

### "99.9 %" defined

A model cannot be 99.9 % *exact* about wind on a future date: weather is chaotic past about 2 weeks. It can be
99.9 % *honest*. Targets:

| Mode | Target |
|---|---|
| Past, lookup | The stored ERA5 value is returned exactly, bit for bit (a test checks it). |
| Past, uncertainty | ERA5 + real ERA5-minus-balloon error profiles, sampled from IGRA. The 99.9 % band holds the balloon-measured value in 99.9 % (99.8–99.95 %) of soundings, per variable and height band. |
| Future, every lead | The 99.9 % band holds the outcome in 99.9 % (99.8–99.95 %) of held-out cases. 68/95/99.7 % as in *Acceptance criteria*. |

Checking a 99.9 % band needs about 10,000 or more independent cases per band. IGRA has about 100 CONUS
stations × 2 soundings a day, so at CONUS scale there is enough. At the pilot's 2 stations it is borderline,
so the pilot checks 99 % and phase 8 checks 99.9 %.

### Falsification

The generator replaces analogs in a lead band only if, on walk-forward years (5 blocks of 3 years, retrained
per block) and held-out IGRA stations, it:
- is no worse on CRPS, energy score and variogram score;
- has lower error on the 99.9th-percentile neighbour difference;
- is never worse than resampled history at 1–3 years.

Otherwise analogs stay the engine there.

## Data

| Part | Source | Why this source |
|---|---|---|
| ERA5 13 standard levels + surface | **Earthmover Icechunk ERA5** on AWS Open Data, `s3://earthmover-icechunk-era5/icechunkV2`, anonymous, CC-BY-4.0. Use group `pressure/temporal` (u, v, t, r, q, z, w, pv on 1000/925/850/700/600/500/400/300/250/200/150/100/50 hPa) and `single/temporal` (u10, v10, u100, v100, t2m, d2m, sp, msl, blh, …). | No CDS queue; time-series tiles. Google's ARCO-ERA5 is chunked one global map per hour, so a CONUS time-series pull reads ~40× more bytes than needed. |
| ERA5 boundary-layer fill: 975, 950, 900, 875, 825, 800, 775, 750 hPa | **CDS** `reanalysis-era5-pressure-levels`, GRIB, area-cut server side, one request per month (744 h × 8 levels × 5 variables ≈ 30k items, under the 60k cap). | The 13-level set has only 1000/925/850/700 below 3 km: at Midland the levels above ground are 10 m, 100 m, ~600 m, ~2.2 km, too coarse for low-level jets and shear. Only these 8 levels come from CDS. |
| Terrain | Copernicus 90 m DEM (or Open-Meteo elevation API) | Site elevation and roughness. |
| ENSO | NOAA CPC monthly ONI (`oni.ascii.txt`) + PMEL warm water volume (`wwv.dat`) | History for fitting; the forecast is a lagged regression on both (no plume needed). WWV extends useful skill from ~6 to ~12–18 months. |
| QBO | NOAA CPC `qbo.u30.index` / `qbo.u50.index` (FU Berlin's file ended 2021) | Predictor for winds ≥ 10 km. |
| Radiosondes | **IGRA v2.2** (NCEI), ~90 CONUS stations | Ground truth for calibration and ERA5-smoothness inflation (phase 6). 12Z/00Z launches only partly overlap 08–20 local. |
| 0–15 day members | Open-Meteo `/v1/ensemble`: `google_weathernext2_ensemble` + `ecmwf_ifs025` (live); WeatherNext 2 archive on Earth Engine / BigQuery (2022+, CC-BY-4.0) | Two different model lineages for the pool; the archive is the only multi-year member hindcast found. |

**Earthmover store, checked 2026-11-03** (opened with `icechunk` 2.3.1, anonymous): branch `main`, hourly
from 1940-01-01 to 2026-06-30 (758,232 steps). Temporal chunks are **8,736 h (~1 year) × 1 level × 12 × 12
grid points (3° × 3°)**; arrays use the `pcodec` codec, so reading needs `pip install icechunk xarray zarr
"numcodecs[pcodec]"`. RH (`r`) and geopotential (`z`) are stored, so nothing has to be derived. Measured from
this machine: ~3–5 s per chunk; one year of all 13 levels at one tile took 78 s.

Download estimates at that rate (5 variables × 13 levels × 35 years per 3° tile ≈ 2,300 chunks):
- **Pilot** (6 tiles covering the box; Midland's neighbours straddle a tile edge): ~16k chunks, 1–2 h with 16 parallel reads. Run from this machine.
- **CONUS** (~170 land tiles): ~400k chunks, about two weeks from home. Run it on a small VM in AWS
  us-east-1 (same region as the bucket, no egress fee for the read), write the reduced store, download that.

**Store layout.** Zarr, chunked by spatial tile × full time axis, so a query reads 4 small chunks.
Sizing for CONUS (≈ 13k points, 35 years, solar 06–21 h, 44 heights × 4 variables + 3 surface (10 m wind is the first profile height) = 179 values,
float16): raw profiles ≈ 1.1 TB; with 32 vertical EOF coefficients per profile ≈ 200 GB; every 2nd day ≈
100 GB, still ~750 analogs per point. The **pilot keeps raw profiles** (~10 GB, no compression); EOF
compression comes only at CONUS scale (phase 8).

## Acceptance criteria (replaces "99.9 %")

All are measured with leakage-free backtests: **walk-forward by year** (predict year Y using only years < Y,
with a ≥ 45-day gap) and, at CONUS scale, **spatial blocks** (5° × 5° checkerboard with buffers) for unseen
sites. Coefficients, EOFs and inflation factors are refitted inside each fold.

| Criterion | Target |
|---|---|
| Calibration | ±1/2/3σ (and 5–95 % bands) hold 68/95/99.7 % (90 %) of outcomes within ±3 points, per variable, height band and lead band; PIT histograms flat. 99.9 % band holds 99.8–99.95 % of IGRA outcomes (checked at CONUS scale, phase 8). |
| Past dates | Lookup returns the stored ERA5 value exactly; the uncertainty bands meet the calibration row against IGRA. |
| Skill | CRPS ≤ plain stationary climatology at every lead (CRPSS ≥ 0); > 0 where a predictor was kept. Expect ~0.02–0.08 at 1–3 years, more for temperature and jet-level winds, near zero for low-level wind and RH. |
| Profile realism | Energy score and variogram score (p = 0.5, on 100 m–1 km shear layers) better than independent per-height sampling with the same mean/std, i.e. v1's output. Vertical shear spectrum matches radiosondes. |
| Speed | Site lookup ≤ 50 ms; 1,024 draws < 1 ms. |
| Reference | Not worse than NASA Earth-GRAM on held-out IGRA soundings (phase 9 benchmark). |

## Workflow

```
tempest --lat 32.99 --lon -106.97 --date 2027-06-16 --time 09:00 --samples 1024
```

Writes:
- `site_<date>_monte_carlo.toml`: same format as `dynamics`' (mean and std per variable), plus
  `[wind_profile]` (heights and mean/std arrays for u and v) and a `source` line naming the path, the
  predictors kept and the calibration version.
- `site_<date>_profiles.npz`: N × heights × variables samples, for the sim's future profile wind model.

## Phases

| # | Phase | Done when |
|---|---|---|
| 0 | Decisions | done 2026-11-03 (see *Decisions*) |
| 1 | **Pilot data** (build spec: [PHASE1.md](PHASE1.md)): Earthmover temporal store (6 tiles covering the box) + CDS boundary-layer fill (box 31–34 N, 108–101 W, 420 monthly requests) → profiles on the above-ground grid at Spaceport America and Midland, 1991–2025. **Queue the CONUS CDS fill right after the pilot box, in the background**: it takes weeks. **Start the daily forecast logger** (WeatherNext 2 + IFS ENS members at both sites, one script on a scheduled task) so phase 5 has verification data. | pilot profiles spot-checked against the `dynamics` Open-Meteo tool and against IGRA soundings at Santa Teresa (72364) and Midland (72265) |
| 2 | **Scoring harness, before any model**: CRPS, energy score, variogram score, PIT/coverage; walk-forward splits; baseline = v1-style independent mean/std climatology | harness reproduces known numbers on the baseline |
| 3 | Analog sampler (no trend yet), drawing across years with a cap per year so samples are not dominated by a few look-alike years (SARAF, arXiv 2606.04135) + spatial blend + elevation correction + mean/std/TOML output. Keep a surface value + neighbour-difference view of each profile for phase 6 (*Optimal structure* S4) | beats the baseline on energy and variogram score; calibrated on held-out years |
| 4 | Year trend, ENSO, QBO shifts + predictor-uncertainty draws. Also test the alternative: weight analogs by how close each year's ONI/QBO is to the drawn target value (a Gaussian kernel, with bandwidth tuned on the backtest), and keep whichever scores better. Predictor-forecast contender: Chronos-2 (Amazon's 2025 time-series foundation model, Apache-2.0, zero-shot, runs on CPU) against the ONI + WWV / QBO regressions. Draw predictors by Latin hypercube, not at random (option 1B). Coefficient contender (option 1C): partial pooling across neighbouring heights and points instead of a per-point keep/drop (arXiv 2606.23009) | each kept term passes |t| ≥ 2 **and** improves walk-forward CRPS; coverage holds out to 3 years |
| 5 | Near-term (WeatherNext 2 + IFS ENS pool, each source calibrated then the pool; day 10–15 blend) and past paths | matches the `dynamics` tool's means; calibrated on WeatherNext 2 archive hindcasts (2022+) and the logger's data, with bias fitted on recent years only (AI models trained on past climate run 15–30 years cold, arXiv 2509.22359); pool beats each model alone on CRPS and energy score, else keep the better one. Pool recipe: option 1D (EMOS per model, weights shrunk toward equal, arXiv 2509.04203) |
| 6 | Calibration: spread inflation per (variable, height, lead band), then **online conformal prediction** on top (it guarantees coverage with no distribution assumption and fixes AI ensembles' coverage in the tails; arXiv 2606.19642). Calibrate wind as a (u, v) vector, not two separate scalars (arXiv 2610.35137). ERA5-smoothness correction from IGRA. Fit generalized-Pareto tails beyond the analog set's 99th percentile, so 99.9th-percentile shear is not capped by history (huge-ensemble study arXiv 2510.08893); new extreme profiles keep the shape of a real extreme event, scaled by a GPD radius (arXiv 2509.26451). Last step: reorder calibrated values to the raw analog rank order, so calibration keeps the joint shape (arXiv 2608.12998). Online updates use only verifications whose target time has passed (arXiv 2605.17250). **Then test *Optimal structure* S4–S7** (difference-space station quantile map + GPD, rank reorder, MinT reconcile, whole-cloud conformal scaling); keep it if it passes its falsification test | coverage criteria pass on radiosondes, not just on ERA5 |
| 6A | **Neural generator (3A)**, see *Engine decision*: train on station-corrected pilot profiles on the RTX 4090; same calibration path as analogs; router per lead band | passes the generator falsification test against the phase 4–6 analogs, per lead band (bands where it fails keep analogs) |
| 7 | CLI, lookups (elevation, timezone, ONI/QBO feeds), samples file | end-to-end on random pilot-region points |
| 8 | Scale to CONUS: merge CDS boundary layer, EOF compression, full store; spatial-block CV; add 3C (station correction for any point) and retrain the generator on its output, kept only if 3A + 3C beats 3A + nearest-station correction on held-out blocks; 99.9 % coverage check on all CONUS IGRA stations | criteria hold on held-out blocks; store fits on one SSD |
| 9 | Optional, each gated by the backtest: Earth-GRAM benchmark (NASA GRAM Suite, has a Python API, Linux/WSL); seasonal anomaly shift for months 1–6 from C3S/SEAS5, and weeks 3–6 by **forecast-conditioned analog reweighting**: weight the analogs so their near-surface statistics match a bias-corrected EC46 forecast (Open-Meteo seasonal API, near-surface only). The correction is learned from past forecasts, as in probabilistic bias correction (arXiv 2604.16238), which won ECMWF's 2025 subseasonal competition. A learned weight mask for analog selection (arXiv 2506.14022; the multi-year version 2502.17583 matches initialized climate models at 1–10 years); train it on a large simulated library, not on 35 ERA5 years. Alternative ML generators if 3A (phase 6A) falls short. Recipe: simple backbone, MAE pre-training then short CRPS + energy + variogram fine-tuning in EOF space (arXiv 2604.09041, 2601.18111); pre-train on a long emulator run (ACE2, Apache-2.0) if 35 years overfit (arXiv 2512.22814) | each one beats the phase 8 system on the scores above, or is dropped. Contenders from *Options by complexity*: 3D first (one-week probe), then 2B, 2C, 3B (3C moved to phase 8) |

## Known risks

- **CDS queue.** Boundary-layer levels come from CDS, where pressure-level queues have run to hours or more
  per request in 2026. Mitigation: start in phase 1 with the small pilot box; phases 2–4 can run on the
  13 Earthmover levels while the fill arrives, then rerun once it lands.
- **IREC venue.** IREC moved from Spaceport America to Midland in 2025; the sim still points at Spaceport
  America. The pilot covers both, and nothing in the method is site-specific.
- **ERA5 is too smooth**, most of all for wind: spreads run low. Phase 6 corrects against radiosondes.
- **Long-range limits.** Beyond ~2 weeks the output is a distribution, not a forecast. Skill over
  climatology is small (a few %), mostly temperature and jet-level winds.
- **QBO disruptions** (2016, 2020) break its regular period; the QBO term is kept only while backtests say
  it helps, and its forecast spread widens with lead.
- **Tails.** Resampled history cannot produce a profile more extreme than history plus the shift. Check the
  99th-percentile shear against IGRA in phase 6. Phase 6's Pareto tails are the first fix; phase 9's
  generator is the second.
- **Forecast archive gap.** No long archive of IFS ENS members was found on Open-Meteo. Start the
  logger early, and if Earth Engine access is refused, calibrate the pool on the logger's data alone. AI
  ensembles' gains for wind shrink at deep tails and long leads (arXiv 2610.25545), so verify the tails on
  their own.
- **FS integration later.** The sim's only wind model in configs is `UniformWind`; using `[wind_profile]` or the
  samples file needs a new wind model in `flight_sim`. Out of scope here.

## Design review before first training (2026-11-04)

Fixed in code:
- Constant input columns (e.g. one training year) no longer get a ~0 scale; that blew validation loss up.
- 10 m wind was a target twice (profile + surface); now once. RH is clipped to 0–100.
- Normalisation stats come from a 1M-row sample, so 8M rows fit in 31 GB RAM.

Open, in priority order (items from GPT-suggestions.md / suggestions-copoilet.md marked G/C):
1. **Targets are ERA5, not radiosonde-corrected** until phase 6. First models will be under-spread, mostly wind.
2. **CDS fill merge written** (`to_heights.cds_levels`, checked on 1991-02: levels interleave correctly, profiles change only below ~2.5 km). Waiting for all 420 months, then rebuild to `profiles_bl.zarr` / `pilot_bl.npz`.
3. ~~Year feature extrapolates~~ **Done:** year left the main network; it enters a separate learned path,
   output += slope(place, season, hour, height...) x year. Past 2025 the model follows that learned straight line.
   Caveat: Pinatubo (1991-93 cooling) sits at the start of the record and can tilt the slope; check per-height
   slopes after the first run.
4. **Climate indices (ONI, WWV, QBO) enter as straight-line effects only** (fixed 2026-11-04). Fed into the
   main network, their four monthly values fingerprinted each month: on the real data held-out error rose from
   step 500 (0.50 -> 0.65 by step 3000) while training error fell. As slope(place, season, hour) x index, like
   the year trend, held-out error falls steadily (0.4858 at 3000 steps vs 0.4871 without indices). Still open:
   query-time indices are forecasts while training uses observed values (G C9, C #4); the scorecard's
   "drivers unknown" column measures that case. Indices change only the mean so far, not the spread.
5. **m = 4 samples per row** (what AIFS-CRPS uses; the almost-fair CRPS removes most of the small-m bias).
   Still check PIT per height after the first run (G F18).
6. **Loss weights every target equally**: 44 wind heights outweigh 3 surface values. Check per-variable
   scores before reweighting (G F19).
7. **Rows are correlated** (neighbouring hours/points): validate by whole years, never random rows (C #10).
   Already done: last 3 years held out.
8. **Physics checks**: hydrostatic height test (G A5), shear at 99th percentile vs IGRA (G F20).
9. **Scale**: the npz is held in RAM. Fine for the pilot (~6 GB); CONUS needs streaming.
10. ~~IGRA host down~~ **Done:** both stations downloaded 2026-11-04 (Santa Teresa, Midland; zips verified).
11. **No lapse-rate cap**: measured on the pilot store, 13-level ERA5 profiles cool faster than dry-adiabatic
    (9.8 K/km) in 31 % of rows at 200-300 m, 10 % at 0.75-1 km, 2 % at 1.5-2 km (linear interpolation from the
    2 m value on hot afternoons). A cap would fight the training data; revisit after the CDS merge.
12. **Pressure**: only surface pressure (sp) is a target now. Add pressure-at-height as a 5th profile variable at
    the CDS-merge rebuild (needs `to_heights` + dataset rebuild).
13. **elev_site = elev_grid** in every ERA5 training row, so the site-elevation input carries no information
    yet. Query with elev_site = elev_grid until phase 6 trains on station-corrected targets.
14. **Phase 6 station correction (S4), as built** (`tempest.calibrate.station`): per (station, season, 00Z/12Z,
    variable, height) balloon ~ a + b·ERA5, plus one whole leftover profile (balloon minus line) resampled from
    the same group. The first try, a per-step quantile map in difference space, matched the steps but inflated
    whole-profile spread 20-140 % (ERA5's smooth steps lean the same way and add up), so it was dropped.
    Held-out 2023-2025 (4,208 soundings), ERA5 -> corrected: level gap u 0.45->0.22, v 0.42->0.24, T 0.51->0.22,
    RH 7.1->2.4; 99th-percentile shear ratio u 0.58->0.84, v 0.50->0.82, RH 0.77->0.96; spread ratio stays
    0.98-1.01. Shortcuts: two stations stand in for the box (nearest wins), two launch hours for the day,
    leftovers only from fit years (no GPD tails yet); surface t2m/sp/rh2m are not corrected.
15. **Site elevation** (PLAN line 82) is applied at query time: `sample.to_site` moves t2m (6.5 K/km) and sp
    (hypsometric) from the grid to the site elevation; profiles are above ground and stay. Training keeps
    elev_site = elev_grid (item 13).
16. **Balloon scorecard** (`tempest.scoring.score` twin, `tempest.scoring.sonde`): held-out 00Z soundings
    (~17 h local; 12Z is outside the training window) at both stations vs balloon climatology and a Gaussian.
    First look (partly trained ERA5-only model): RH above 5 km and surface pressure lose to climatology, i.e.
    ERA5's upper-air humidity and grid elevation differ from the balloons; the station-corrected model and
    item 15 target exactly these.
17. **CDS boundary-layer fill is slow**: about 1 month per 30 min, so ~9 days for 420 months. Phase 6 runs on the
    13-level store meanwhile; the pipeline rebuilds, refits the station map and retrains when CDS completes.

Scorecard: `python -m tempest.scoring.score --model ... --data ...` scores held-out years in physical units
(CRPS, 90 % coverage, skill vs same-point/month/hour climatology), drivers known and drivers unknown, next to
a NASA Earth-GRAM-style baseline (monthly mean + correlated bell-curve spread) and a variogram score for
profile shape.
CDS fill: the first month (1991-02) was checked on 2026-11-04: 8 levels, hourly, 13 x 29 points, as requested.
Validation loss during training is now computed on rebuilt profiles, not on the differences.

## Improvement log (from 2026-11-04; goal: 99 % of past values inside the 99 % range, everywhere)

Coverage is now counted with order statistics (k = round((1-p)/2·(m+1)) from each end), so a perfect ensemble
scores exactly p; interpolated quantiles undercounted (m = 100 scored 0.97 at 99 %). Test years 2024-2025 only;
2023 (first validation year) is reserved for fitting calibrations. Diagnostics (`tempest.scoring.diag`, run by
score and sonde): bias, spread/skill, which side of the 99 % range misses, worst columns, coverage by month and
station; training logs per-variable validation CRPS, spread/skill, bias, gradient size and learning rate.

| # | change | test | result |
|---|---|---|---|
| 1 | sp learned as departure from standard pressure at grid elevation | balloons | sp skill -0.072 -> -0.010 |
| 2 | step loss (CRPS on height-to-height steps, weight 0.5), model st2 | balloons | variogram v -0.087 -> -0.034, u/T/RH positive |
| 3 | range calibration on ERA5 2023 (`tempest.calibrate.spread`), st2 | ERA5 2024-25 | 99 % coverage 0.980-0.997 per band (raw cov90 0.83-0.88); CRPS skill unchanged |
| 3 | same | balloons 2024-25 | 99 % coverage 0.982-0.997; misses: RH 11-13 km high side (spread/skill 0.76), T 5-7 km (0.84) |
| 4 | extra balloon calibration fit on 2023 soundings, pooled per variable x band, on top of #3 | balloons 2024-25 | **rejected**: T 1-5 km 0.989 -> 0.979, RH 1-5 km 0.997 -> 0.983, T/rh2m CRPS worse; one year's quirks (u median shift ~1.4 m/s) don't carry over |
| 5 | range calibration fit on 5 years (2019-2023, 60k rows) instead of 2023 only | ERA5 + balloons 2024-25 | **kept** (`--from-year 2019`): ERA5 worst column T 5-12 km 0.963 -> 0.982, T 1-5 km 0.966 -> 0.982, CRPS skill equal or better almost everywhere; balloons T 1-5 km 0.989 -> 0.994, T 5-12 km 0.983 -> 0.988, T skill +0.01-0.035; RH 12-18 km skill 0.002 -> -0.014 |
| 6 | ERA5 RH converted to liquid-water RH (`to_heights.liquid_rh`; IFS mixes ice in below 0 C, balloons report over water) | ERA5 vs balloons 2023-25 | raw bias above 5 km -8..-16 % -> ~-1 %; after the station line fit only 0.03-0.09 % rmse better (the fit already absorbed it). **Kept** for the full-data rebuild: free there, and the big fix for anywhere without a nearby station |
| 6b | station line fit on recent years only (2005+ / 2013+, newer radiosondes) | same | **rejected**: worse 5-13 km (bias +2..+5 %), better only 13-18 km |
| 7 | station correction leftovers drawn from soundings with similar ERA5 moisture (tercile of RH 5-13 km) | balloons 2023-25, fit 1991-2022 | **kept**: RH CRPS 9-13 km 5.78 -> 5.34, 13-18 km 4.17 -> 3.84, v 9-13 km -1 %, others equal; 99 % coverage -0.001..-0.003 (range calibration absorbs it). Applies from the next station-map fit (full-data pipeline) |
| 8 | range calibration split by season, or by spread tercile (instead of one global map) | ERA5 fit 2019-23, test 2024-25, 5k rows, m=199 | **rejected**: mean cov99 global 0.992 / season 0.990 / spread 0.991; worst band 0.973 / 0.967 / 0.970; CRPS +0.2 % / +0.1 %. Splitting thins each map's 99 % tail more than regimes differ |
| 9 | GPT-suggestions parts 2-4: fixed validation noise (same noise at every early-stop check, training RNG untouched); calibration file refuses a different member count, score/sonde default --m to the calibration's m; liquid-RH continuity test | - | **added**: val noise moved the val loss by ~0.002 between checks (same size as real gains), so early stopping partly picked lucky checkpoints; effect shows at the next training. Rest triaged into docs/FUTURE_OPTIONS.md |
| 10 | baseline retrained without station correction (generator_pilot13sp, same settings/sp fix) vs st2 | ERA5 + balloons 2023-25, m=50, uncalibrated | **st2 kept**: vs ERA5 the plain model is level or slightly better (skill RH 0.018 vs 0.011, T 0.076 vs 0.068), but vs balloons it loses badly (RH skill -0.28 vs 0.00, T 0.041 vs 0.057): the station correction is worth far more than its small ERA5 cost |
| 10b | bug: station `apply` gathered a whole leftover pool per row (369 GB on the pilot build) | build_dataset with the moisture map | **fixed**: gather one drawn profile per row; same draws, tiny memory. Would also have crashed the full-data pipeline build |
| 11 | moisture-tercile station leftovers (item 7, generator_pilot_mt, fixed val noise) vs st2, both with the 2019-23 range calibration | ERA5 + balloons 2024-25, m=199, calibrated | **rejected, st2 kept**: balloons upper RH improves (5-12 km miss 0.92 -> 0.53 %, 12-18 km 1.56 -> 1.24 %) but balloon mean miss gets worse (0.94 -> 1.10 %, t2m and upper wind worse), ERA5 RH 15-18 km low-side misses jump to 3-4 % per column, and mean CRPS skill drops slightly on both (ERA5 -0.0121 -> -0.0135, balloons -0.0136 -> -0.0141). The split pools are thinner and add noise; code stays (old one-pool maps still load) |
| 12 | balloon range calibration fitted on 5 years (2019-23, 2,591 soundings; new `sonde --station-calib-from-year`) on top of the 2019-23 ERA5 calibration, st2 | balloons 2024-25, m=199 | **rejected**: surface gets better (t2m cov99 0.988 -> 0.997, sp, rh2m) but RH collapses where one pooled band map hides different columns: RH 12-18 km 0.984 -> 0.965 (spread/skill 0.76), RH 0-1 km 0.996 -> 0.984; both stations' overall cov99 drop (0.989 -> 0.987, 0.991 -> 0.990). Option kept for a per-column fit once more balloon years exist |
| 13 | afCRPS alpha 0.99 instead of 0.95 (generator_pilot_a99, new `crps_alpha` setting, fixed val noise) vs st2, both with their own 2019-23 range calibration | ERA5 + balloons 2024-25, m=199, calibrated | **rejected, 0.95 kept**: calibrated miss rates look better (ERA5 mean 0.61 -> 0.59 %, balloons 0.94 -> 0.76 %) but CRPS skill does not move on ERA5 (mean 0.0314 -> 0.0315) and drops on balloons (0.0166 -> 0.0158, RH 12-18 km -0.014 -> -0.026); balloon band cov99 0.9906 -> 0.9911, ERA5 unchanged. Within noise and confounded with the val-noise change, so not a genuine gain. `crps_alpha` stays as a setting (default 0.95, configs/generator_a99.toml) |
| 14 | balloon range calibration fitted on 2019-23 with one map per column (179) instead of per variable x band, st2 | balloons 2024-25, m=199 | **rejected, flag removed**: worse than no balloon calibration on every summary (band cov99 mean 0.9906 -> 0.9890, bands under 0.99 7 -> 8, RH 12-18 km 0.984 -> 0.965, stations 0.989/0.991 -> 0.986/0.989; skill 0.0166 -> 0.0168 is noise). With items 12 and 14 the lesson is that 2019-23 balloons want narrower ranges than 2024-25 needs: the gap drifts between years, so a balloon-fitted map does not carry forward |
| 15 | ERA5 range calibration fitted on the latest 3 years (2021-23, 60k rows) instead of 2019-23, st2 | ERA5 + balloons 2024-25, m=199 | **rejected**: worse on both (ERA5 band cov99 mean 0.9919 -> 0.9916, bands under 0.99 4 -> 6, T 5-12 km 0.986 -> 0.984; balloons 0.9906 -> 0.9898, u 0-1 km 0.984 -> 0.981; skill 0.0314 -> 0.0312 and 0.0166 -> 0.0161). The ERA5 shortfall is not year-to-year drift; a narrower fit window only adds noise |
| 16 | ERA5 range calibration on 150k rows of 2019-23 instead of 60k, st2 | ERA5 + balloons 2024-25, m=199 | **rejected, 60k kept**: coverage edges up (ERA5 band cov99 mean 0.9919 -> 0.9922, bands under 0.99 4 -> 3; balloons 0.9906 -> 0.9910, stations 0.989/0.991 -> 0.990/0.992) because the range ends widen (median scale 1.07/1.10 -> 1.08/1.11), but CRPS skill drops (ERA5 0.0314 -> 0.0311, balloons 0.0166 -> 0.0151). Items 15-16: the calibration fit is saturated; the last few tenths of a percent are within noise of 2 test years |
| 17 | diagnostic: month-block bootstrap (12 calendar months, 20k resamples) of 99 % coverage per variable, st2 + 2019-23 calibration | ERA5 + balloons 2024-25 | **no change**: every balloon variable's 95 % interval contains 0.99 (t2m 0.987 [0.978, 0.994], u 0.989 [0.984, 0.993]), so no balloon shortfall is real at this sample size. Only ERA5 T is likely short (0.9885 [0.9854, 0.9913]): T 5-6.5 km misses both sides equally with spread/skill 0.89-0.92, worst in Jan-Mar and June, i.e. ranges slightly too narrow there, not shifted. Next real gain needs the model (more training data from the CDS years), not more calibration tuning |
| 18 | audit (no model change): over/underfitting, leakage, and GPT part-5 claims | code + training logs + st2 score log | **findings**: no overfitting (train ~0.716 vs val ~0.725, val flat after ~1500 steps: input-limited, more capacity will not help). Real problems: (a) st2/a99/mt trained without `--max-year`, so val 2023-25 overlapped the 2024-25 test years and picked the early stop; (b) range calibration fitted on 2019-23, mostly training years, so ranges slightly narrow; (c) 17 decisions made on 2024-25, so they are development years; (d) cold T bias (val -0.07 to -0.10 std, test -0.2 to -0.37 K): year slope under-extrapolates warming. GPT part 5: CRPS 'not comparable across m' is wrong (all four methods use the same m; sorted formula is exact for the ensemble); 'k=1 of m=199 gives ~100 %' is wrong (198/200 = 0.99, tested); 'known drivers flatter the headline' is true in principle but immaterial (known vs unknown skill and cov99 differ by <= 0.01 in every band); 'ERA5 truth flatters coverage' is true by design, balloons are the real test; test-year reuse is true (= c). Added: whole-profile 99 % coverage line in score.py (per-column coverage hides joint misses); climatology itself reaches cov99 0.97-0.99, so per-column cov99 is a weak bar and CRPS skill (0-9 %) matters more. Fix: honest protocol from now on: train <= 2020, val 2021-23 (`--max-year 2023`), calibrate on 2021-23, dev test 2024-25, final untouched test 2026 Jan-Jun (`--last-test-year`). |
| 19 | station correction fitted on balloons 1991-2020 instead of 1991-2022 (default `--last-year` now 2020; `models/station_map_2020.npz`) | balloons 2021-25 held out | **kept (leak fix)**: the old fit used validation years 2021-22. Held-out 2021-25 gap still closes: level gap u 0.41 -> 0.18, v 0.38 -> 0.20, T 0.51 -> 0.17, RH 7.9 -> 2.5; step gap u 0.95 -> 0.32. Full-data pipeline restarted as v3 with `--max-year 2023`, calibration 2021-23 and test 2024-25 (the old pipeline.sh and pipeline2.sh, both still waiting, are stopped; the CDS downloader keeps running). |
| 20 | block validation option (`val_block_frac`, `configs/generator_blocks.toml`): validation = 10 % of 14-day blocks drawn from every year, rows within 3 days of a block dropped from training; default off (tail years as before) | queued: train `--max-year 2022` with blocks, calibrate 2023, test 2024-25 then 2026 Jan-Jun, against the tail-split B0/A5 models | **pending**: lets training see recent climate (drift) while 2024-25 and 2026 stay untouched; a unit test checks the 3-day gap and that the old split is unchanged. |
| 21 | training speed: the 4 members train side by side in one loop (training rows normalised once and kept on the GPU in float16, forward pass in bfloat16, fused AdamW), `steps` 20000 -> 6000 to fit a 15-minute budget | timing on pilot_st.npz; accuracy: B0 of A5 (6000 steps) vs B0 retrained with `configs/generator_slow.toml` (20000 steps), same data and split, ERA5 + balloons 2024-25 | **kept 6000** (2026-11-04): 20000 steps vs 6000 on ERA5 2024-25 (`data/slowcheck_score.log` vs `data/rescore_score_b0.log`): every band's skill and 99 % coverage agree within the day-block intervals (largest gap: u 12-18 km skill15 unknown 0.052 vs 0.045, intervals overlap). Longer training buys nothing measurable. Speed measured: 4-member step 125 ms (was ~208 ms one member after another), so ~13 min for 6000 steps; 20000 steps would still take ~42 min because the GPU is now full (torch.compile is not available here: no Triton on Windows). The 6000-step cut is reverted if the 20000-step model is clearly better. |
| 22 | A5: training years 1980-2020 (pilot80, 47 blocks) instead of 1991-2020 (B0), same code, 6000 steps, honest split, each with its own 2021-23 range calibration | ERA5 + balloons 2024-25, m=199 | **rejected, B0 kept**: T gets worse on both (ERA5 known skill 0-1 km 0.082 -> 0.074, 1-5 km 0.081 -> 0.072, 5-12 km 0.098 -> 0.092; balloons 0.046 -> 0.037, 0.044 -> 0.037, 0.079 -> 0.073), u slightly better (ERA5 0-1 km -0.008 -> -0.003, balloons 1-5 km 0.007 -> 0.019), and ERA5 whole-profile RH coverage drops 0.880 -> 0.820. Older years pull the learned warming trend down (the cold T bias, item 18d) more than the extra data helps. First run with the best-guess error table (A5, ERA5): T MAE 2.5-3.6 K vs climatology 2.7-4.0 K; u 5-12 km 9.3 vs 9.6 m/s; RH 0-1 km 14.2 vs 14.8 %. No error bars yet (Evaluation review E3) |

## A6 and other drivers: inputs the user never gives (plan, 2026-11-04)

The tool is called with only place and time. Every driver must be fetched by the tool itself, and at query time
only **values up to now** exist: no future soil moisture, SST or index values. So each driver is trained the
way it will be used.

**Finding:** today's `oni`, `wwv`, `qbo30` and `qbo50` inputs use the value for the *target* month, which is
unknown for a future date. The same fix applies to them.

**How to use a driver we only know up to now (options):**
1. **Lagged input (chosen).** During training, each row gets the driver value from `lag` days before the target
   date, plus `lag` itself as an input.
   - `lag` is drawn at random from 0-180 days, so the model learns how fast each signal fades.
   - At query time, `lag` = target date minus the latest available value.
2. **Damped persistence (fallback).** Use anomaly x exp(-lag / tau) as one input, with tau fitted per driver.
   This is the same information with fewer free parameters. Use it if option 1 overfits.
3. **Driver forecasts** (CPC/IRI ENSO plume, NMME or C3S SST and soil moisture): these are available, but the
   archives of past forecasts are short and inconsistent. Moved to phase 9.
4. **Unknown or very long lag.** A "driver missing" flag is set at random in training (about 10 % of rows), so
   one model also answers with no driver and falls back to today's behaviour.
5. **`uncertainty` kind.** The driver value at the target date is drawn from history: past cases with a similar
   current value, followed forward by `lag` days. This replaces the plain random ENSO/QBO/solar draws in
   `TOOL_PLAN.md`.

**Candidates, all fetched automatically for free.** None counts as certain until it passes the held-out test.
They are ordered by the strength of published evidence:

| # | Input (fetched by the tool) | Source, delay | Expected effect | Confidence |
|---|---|---|---|---|
| 1 | Recent local departures from normal of the targets themselves (mean T, RH, u, v over the last 7 and 30 days at the site; surface + a few heights) | ERA5 store / Open-Meteo archive (~5 days behind) + Open-Meteo `past_days` for the last days | persistence is the strongest known predictor for weeks 3-8, mostly T and RH near the ground; fades with lag | high at lags < ~45 d |
| 2 | Soil moisture, top layers (A6) | ERA5 `swvl1`-`swvl2` (same store) / Open-Meteo soil moisture | well-documented weeks 3-8 skill for 2 m T and humidity over semi-arid land in summer (GLACE-2); little above ~3 km | high for surface and boundary layer |
| 3 | Regional SST: Gulf of California, Gulf of Mexico, east Pacific off Baja (A6) | NOAA OISST v2.1 daily via ERDDAP (~1-2 days behind) | monsoon moisture, Jun-Sep RH and T | medium |
| 4 | MJO (RMM1, RMM2) | Australian BoM daily index (~1-2 days behind) | weeks 2-5 signal; weak over the Southwest | medium-low, mode 3 only |
| 5 | Stratospheric polar vortex (10 hPa zonal wind at 60 N) | ERA5 store | winter weeks 3-8, mainly upper levels | low-medium |
| 6 | Snow depth upwind (southern Rockies) | ERA5 `sd` | spring T near the surface | low for the pilot box |

Dropped: PDO (mostly carries ENSO, which is already in) and CO2 (the year trend covers it).

**Test (each candidate, one at a time, starting with 1 and 2):**
- Train on years up to 2020, choose on 2021-23, report on 2024-25.
- Report by lag band (15, 30, 60, 90 and 180 days) against the same model without the input.
- Keep it only where CRPS improves at those lags and the 99 % range still holds 98.5-99.5 %.
- The existing indices get the same lag treatment and the same test.

**A6 results so far (2026-11-04): ceiling checks before any retrain.** At the two balloon stations' grid points, 00Z,
I computed the correlation of the 30-day mean departure from normal (ending `lag` days before) with the departure on the
target day. Normals came from 1991-2020. Each cell reads fit years | 2021-25.
- **Candidate 1 (persistence of the targets): rejected for mode 4.**
  - Lag 15-30 days: t2m +0.09..+0.14, rh2m +0.12..+0.19, T at 1.5 km +0.08..+0.14, RH at 1.5 km +0.05..+0.12.
  - 5 and 10 km: at most +0.10 in the fit years and at most +0.06 in 2021-25.
  - Lag 90-180 days: about 0, often with the opposite sign in 2021-25 (for example t2m -0.05, rh2m -0.12 at lag 180).
  - For a near-Gaussian target, r = 0.15 narrows the spread by about 1 % (1 - sqrt(1 - r^2)), so CRPS gains well under
    1 %. That is below the day-block intervals (about ±0.01-0.02 skill), so a retrain could not show it.
  - It stays in the mode-3 plan (`TOOL_PLAN.md`, lags of 1-7 days), where it is much stronger.
- **Candidate 2 (soil moisture swvl1/swvl2, ERA5 `single/temporal`): rejected for mode 4.**
  - Lag 0: rh2m +0.24..+0.29, t2m -0.16..-0.19. This is the same-day link, which is not usable for a future date.
  - Lag 30: rh2m +0.09..+0.16, t2m -0.05..-0.10, 1.5 km at most ±0.12.
  - Lag 60 and beyond: |r| ≤ 0.12, with sign flips in 2021-25.
  - JJA at lag 30, where GLACE-2 expects the most: t2m -0.06 / -0.13, rh2m +0.03 / +0.13. Same ceiling as candidate 1.
- **Existing indices:**
  - On balloons 2024-25 (E12 model), known minus unknown skill15 is at most 0.021 (T 1-5 km and T 12-18 km, t2m 0.020).
    The mean is 0.007. That is the most the indices can add, even with the true target-month value.
  - Next test, no retrain: the model gets the index value persisted from `lag` days before the target. It is scored
    as "unknown" for lags of 15/30/60/90/180 days (`data/a6lag<lag>.log`).
  - **Result (balloons 2024-25, mean skill15 over the 19 bands):**

    | Drivers | Mean skill15 |
    |---|---|
    | true target month (`known`) | 0.0125 |
    | persisted, lag 15 | 0.0111 |
    | persisted, lag 30 | 0.0105 |
    | persisted, lag 60 | 0.0080 |
    | random draws (today's `unknown`) | 0.0056 |
    | persisted, lag 90 | 0.0054 |
    | persisted, lag 180 | -0.0008 |

    - Coverage stays at mean |cov99 - 0.99| 0.0028-0.0037 at every lag.
    - Gains: T 1-5 km 0.011 → 0.035 and T 12-18 km -0.004 → 0.014 at lag 30-60.
    - Losses: one fixed value hurts low-level RH and u. At lag 60, RH 0-1 km -0.025 → -0.038, rh2m -0.051 → -0.061,
      u 1-5 km 0.023 → 0.006.
    - Next: analog draws (option 5) should keep both: the T gain from conditioning and the spread that RH/u need.
      `data/a6an<lag>.log`, K = 8 nearest past months.
  - **Analog draws (option 5), balloons 2024-25, K = 8:**
    - **Mean skill15** (true value 0.0125, random 0.0056):

      | Lag | Mean skill15 |
      |---|---|
      | 30 days | 0.0130 |
      | 60 days | 0.0124 |
      | 90 days | 0.0124 |
      | 180 days | 0.0103 |

    - **Coverage:** mean |cov99 - 0.99| 0.0032-0.0037 (random: 0.0034). No band moves by more than 0.004.
    - **Against random draws:**
      - Better or equal in 15-17 of 19 bands at every lag.
      - Low-level RH now gains too: at lag 60, RH 0-1 km -0.025 → -0.013 and rh2m -0.051 → -0.036.
      - T keeps most of the gain: at lag 60, T 1-5 km 0.011 → 0.026 and T 12-18 km -0.004 → 0.011.
    - **Caveats:**
      - The per-band gains are inside the day-block intervals (lower bounds about 0.015 below the values).
      - Lag 180 still beats random. This is probably not the indices themselves (persistence at 180 days is
        useless). More likely, analog months come from the recent part of the record (for example the QBO phase, or
        the 2021-23 months in the pool), while random draws mix in older decades.
      - Checking on ERA5 2024-25 (5000 rows, `data/a6era<lag>.log`, `-1` = today's random draws).
  - **ERA5 2024-25 (5000 rows, same seed):**

    | Drivers | Mean skill15 |
    |---|---|
    | random | 0.0275 |
    | known | 0.0284 |
    | analog, lag 30 | 0.0304 |
    | analog, lag 60 | 0.0305 |
    | analog, lag 180 | 0.0282 |

    - Coverage is unchanged: mean |cov99 - 0.99| 0.0026-0.0027.
    - The gain fades with lag, as a real signal should.
    - Analog draws beat the true target-month value. A spread of driver values helps CRPS more than one exact value.
    - Biggest gains:
      - T 12-18 km 0.047 → 0.061.
      - u 12-18 km 0.046 → 0.052.
      - T 5-12 km 0.049 → 0.056.
      - t2m 0.065 → 0.070.
    - Small losses: u 1-5 km 0.042 → 0.038, sp 0.016 → 0.014.
  - **Control (lag 60, K = all 43 same-calendar-month months, no matching): no gain.**

    | Drivers | ERA5 mean skill15 | Balloons mean skill15 |
    |---|---|---|
    | random | 0.0275 | 0.0056 |
    | control | 0.0263 | 0.0048 |
    | analog, K = 8 | 0.0305 | 0.0124 |

    - Control coverage: 0.0027 / 0.0037.
    - So the gain comes from matching on the lagged index values, not from which years are in the pool.
  - **Decision: kept, as the driver rule for the tool (no retrain, no model change).**
    - **Rule:**
      - Mode 4 draws ENSO/QBO/solar with `tempest.ingest.indices.analog(table, times, lag_days, m, rng, before)`
        (K = 8), where `lag_days` = target date minus the latest index month.
      - Above ~90 days the gain is gone on ERA5 (lag 180: 0.0282 vs 0.0275), but it never loses, so it is used at
        every lag.
    - **Headline:** `score.py`/`sonde.py` keep random draws as the "unknown" headline, so earlier numbers stay comparable.
    - **Unit test:** `tests/test_data_pipeline.py::test_indices_analog`.
    - **Probes:** the scratch scripts `score_analog.py` and `sonde_analog.py` hold the scoring that was run.
    - **Not done:**
      - Tuning K.
      - A paired day-block interval on the difference. The gains are consistent in sign but small per band.
    - **A6 candidates 1-2 stay rejected for mode 4** (ceiling above). With this rule the lagged index inputs need no
      retrain, because the model already takes target-month values and the analogs supply plausible ones.

## Blueprint review (2026-11-04: two "99 % past-weather accuracy" write-ups, checked against our numbers)

Helpful, adopted:
- Spread that depends on the weather in the station correction: item 7 (by moisture).
- Liquid-water vs ice RH mismatch between ERA5 and balloons: item 6 above.
- Separate past-weather mode that uses the known synoptic state: already the plan (Past dates: the actual ERA5
  profile at that hour); the generator stays for unknown-weather dates.

Mediocre: moved to `docs/FUTURE_OPTIONS.md` (one list with GPT-suggestions parts 2-4, plus discarded items).

Discarded:
- "50 samples cap coverage at 96 %": already solved (order statistics, m = 199).
- Two-number conformal scaling (tau90 / tau99) or one sup-norm multiplier: our per-column quantile map is a superset
  and keeps the band tight where the model is sure.
- Low-rank Gaussian covariance head replacing the generator: Gaussian tails, loses the skew our calibration
  learns, and would throw away a working model for an untested one.
- Accuracy-loss percentages, latencies and "R^2 >= 0.99 / 30-45 % RMSE cut" claims: no sources, not reproducible.
- The drop-in code (to_heights rewrite, TempestPastAssimilator): different variables and height grid, would break
  the data layout and every saved model.

## Evaluation review (2026-11-04: "are we measuring the right thing?")

Started by the user noticing that no score reported the plain error of the single best guess (fixed: score.py and
sonde.py now print MAE/RMSE of the per-height median, physical units). An outside-style review then found more of the
same kind. Each was checked in the code; fixes are scoring-only unless marked.

| # | Problem | Checked | Fix (order) |
|---|---|---|---|
| E1 | Climatology baseline pools 1980-2023 with no warming trend: about 1.4 K too cold for 2024-25, so T skill is partly "knows it is warmer now" | yes (score.py tr rows; t2m anomaly +1.41 K) | add a recent-years baseline (last 15 training years) and report skill against both |
| E2 | "Known drivers" uses the target month's ENSO (ONI is a centred 3-month mean, so it also contains the next month); on balloons T skill drops 0.044 -> 0.024 (1-5 km) with drawn drivers | yes (indices.py) | MAE for `unknown` too; make drawn/lagged drivers the headline; real fix is A6's lag |
| E3 | No error bars; many decisions rest on 0.005-0.02 differences | yes | block bootstrap by day, 95 % intervals (was already queued as GPT item) |
| E4 | 2024-25 has been used for 17+ decisions, so it is development data now; the 2026 hold-out is Jan-Jun only (no monsoon) | yes | call 2024-25 "development"; add a second walk-forward fold; say plainly 2026 H1 says nothing about summer |
| E5 | Model trained and tested only for solar 06-21 h and 00Z balloons at 2 stations; the tool accepts any hour | yes (build_dataset.py, sonde.py) | tool refuses/warns outside 06-21 solar h and outside the box until night hours are trained |
| E6 | Wind best guess as separate u and v medians makes the speed too low | reasoning | also score wind speed and direction error |
| E7 | Average 99 % coverage hides bad months/heights (balloon RH July 0.953, RH 11-12 km 0.943 all high-side misses); no whole-profile line for balloons | yes | print worst month and column; whole-profile line in sonde.py; try a seasonal range map |
| E8 | The Gaussian (Earth-GRAM-like) baseline ignores the hour, a strawman near the surface | yes | group it by hour bin as well |
| E9 | Range map fitted on known-driver samples, applied to drawn-driver ones (may over-widen) | yes | fit on the kind of samples the tool serves |
| E10 | Balloon test keeps only soundings complete at all 44 heights (about 10 % dropped, likely the extreme ones) | yes (sonde.py `isfinite(...).all`) | score each height on the soundings that have it; report the dropped count |

Order: E1, E2, E3, E7, E8, E10 (scoring only, then rescore B0 and A5 together); E9 and E5 next; E4 is wording and a
second fold; E6 with the tool.

**Done (scoring only, no model change):**
- E1: recent climatology (last 15 years before the test).
- E2: the HEADLINE table shows unknown-driver skill next to known.
- E3: 95 % intervals from a whole-day bootstrap (`diag.headline`, test in `tests/test_calibrate.py`).
- E7 (part): the whole-profile 99 % line for balloons.
- E8: the Gaussian baseline is grouped by grid point x month x 2-h bin.
- Calibration provenance (2026-11-04): `spread.py` now stores `model_sha` (sha256 of the `.pt` file, first 16 hex)
  in each range-calibration file, and score/sonde refuse a file whose hash disagrees with `--model`. Files written
  before this have no hash and load as before (so E12's `calib2021` is not checked). Test: `test_calib_provenance`.
- Source mask (GPT 106/135), checked 2026-11-04 and found to need no split report yet. `profiles80.zarr` was built at
  15:27, when only the early-1991 CDS months were on disk. So only some 1991-92 training months have the 8
  boundary-layer levels; every calibration (2021-23) and test (2024-25) row is Earthmover-only (13 levels). Pipeline
  v4 waits for all 420 months, so its store has a single source. Comparing E12 with the v4 model will therefore show
  what the fill does. A per-source score report is only needed if a store is ever built partly filled again.
- Inference speed (2026-11-04). The generator's forward pass takes 0.22 s per 199,000 samples on the GPU. A cProfile
  of one ERA5 scoring run (270 s in total) puts the time in numpy instead:
  - `score.main` inline: 92 s;
  - `variogram_score`: 67 s;
  - `np.partition` for quantiles: 31 s;
  - `spread.apply`: 29 s;
  - the Gaussian baseline: 15 s.

  Faster sampling would therefore change nothing. `Sampler.__call__` now uses `torch.inference_mode`, and its output
  is bit-for-bit identical. The members-in-one-forward and batching items are dropped. The tool's numpy forward pass
  (T1) gets measured on its own.
- Reproducibility fix: the generator's noise (`torch.randn`) was never seeded. Rerunning E12's ERA5 score moved the
  per-column skill15 by 0.0011 on average, and the mean by 0.0002 (unknown drivers) and 0.0006 (known). That is below
  every decision taken so far (A6 analogs: +0.003). score, sonde and spread now call `torch.manual_seed(--seed)`, and
  seeded reruns are identical. Scores from before this point carry that ~0.001 Monte-Carlo noise.
- Members ablation (2026-11-04; scratchpad `ablate.sh`). E12 was scored with only its first k members, with no
  retrain and the 2021-23 range map refitted for each k. Test years 2024-25, m = 199.

  | k | ERA5 skill15 unknown / known | ERA5 mean \|cov99-0.99\| | balloons skill15 unknown / known | balloons mean \|cov99-0.99\| | balloons whole-profile 99 % u / v / RH |
  |---|---|---|---|---|---|
  | 4 | 0.0275 / 0.0284 | 0.0026 | 0.0056 / 0.0125 | 0.0034 | 0.864 / 0.842 / 0.926 |
  | 2 | 0.0275 / 0.0289 | 0.0026 | 0.0063 / 0.0122 | 0.0035 | 0.873 / 0.837 / 0.929 |
  | 1 | 0.0275 / 0.0291 | 0.0028 | 0.0056 / 0.0119 | 0.0040 | 0.855 / 0.825 / 0.918 |

  Skill does not depend on k: the differences are 0.0007 at most, the size of the Monte-Carlo noise. The extra
  members help only the ranges, a little: 1 member is worse on balloon coverage (0.0040 vs 0.0034) and whole-profile
  coverage (1-1.2 points). 2 members already match 4. So the 4 near-identical members are not a real ensemble: they
  agree on the mean and add only a small amount of spread. Decision: keep 4 for E12 and the v4 run, whose script is
  fixed. A future retrain can use 2 members and spend the saved GPU time elsewhere. Members trained to differ more
  (other seeds and data subsets, or other inputs) are untested.
- Per-height PIT check for E12 (A1, G F18; 2026-11-04, from the `_diag.csv` files, 2024-25, m=199, so each tail
  should catch 1/200 = 0.005 of truths). Most heights are close. The misses:
  - ERA5 T at 5-9 km: the spread is too small (spread/error 0.91-0.93). Truths land above the top member 1.2-1.6 %
    of the time, and cov99 is 0.979-0.980. The model mean is 0.3-0.5 K too cold at 4-12 km (item 18d).
  - ERA5 RH_2500: truths land below the lowest member 2.8 % of the time (cov99 0.970); this is one height only.
  - Balloons: u at 50-100 m has too little spread (0.85-0.90), with each tail at 1.0-1.3 %. RH above 12 km misses
    its high tail 1.5 % of the time (the sensor's dry-top problem, already known).
  - Is the cold T bias a warming trend the model fails to extend? **No.** I measured the raw per-year bias (no range
    calibration, 20k rows a year, scratchpad `yearbias.py`) for 2011-2025. At 5-12 km it was -0.38 K in 2024 and
    -0.53 K in 2025. In training years it already ranged from -0.58 K (2015) to +0.48 K (2012), with no drift over
    time. The 2024-25 values are year-to-year weather the drivers do not explain, not a trend error. So a trend
    boost or year shift has no support, and none was tried. The range calibration fitted on 2021-23 cannot foresee
    a single cold-biased year either.
- Physics check (A3, design review item 8; 2026-11-04, scratchpad `physics.py`). E12 on 2024-25, 4,000 ERA5 rows,
  m=199, compared against the station-corrected targets. Hydrostatic consistency holds by construction: the only
  pressure output is surface pressure, and pressure at height would be derived from T. Results by band, as
  truth / raw samples / calibrated samples:

  | band | median shear (m/s per km) | 99.9th-percentile shear (m/s per km) | share faster than dry-adiabatic | share of inversions |
  |---|---|---|---|---|
  | 0-1 km | 8.9 / 8.8 / 9.1 | 82 / 75 / 80 | 42.9 / 43.9 / 44.1 % | 15.3 / 14.0 / 15.0 % |
  | 1-5 km | 5.2 / 5.1 / 5.2 | 25.7 / 20.3 / 21.6 | 9.8 / 8.5 / 10.6 % | 2.2 / 1.9 / 2.2 % |
  | 5-12 km | 5.3 / 5.1 / 5.2 | 30.3 / 23.4 / 24.0 | 3.5 / 3.8 / 3.7 % | 4.8 / 4.5 / 5.5 % |
  | >12 km | 7.1 / 6.9 / 7.1 | 34.8 / 27.1 / 28.3 | 0.4 / 0.4 / 0.5 % | 32.5 / 34.3 / 34.0 % |

  - Typical profiles are physically right, and so are lapse-rate shapes.
  - Above 1 km, the strongest shear layers (99.9th percentile) are 16-22 % too weak, and calibration recovers only
    a little. The range calibration works one height at a time, so it cannot sharpen a jump between two heights.
  - Why it matters: this does not show up in CRPS or coverage, but it matters for balloon risk (G F20). The balloon
    comparison against IGRA, a shear-aware loss term (for example a CRPS on neighbour differences, which are already
    the outputs) and the hydrostatic penalty all remain options for a future retrain. None is tested.
- A2 (go/no-go launch rule) has not been built. It is a product feature, not an accuracy change, and its thresholds
  (wind, shear, surface limits per balloon type) must come from the user. It belongs with the query tool
  (TOOL_PLAN.md).

The best-guess (median) MAE/RMSE is printed by both scorers. E10 and the worst-month/column print are still open.

**First honest B0 numbers.** CPU check: balloons are all 2024-25 00Z soundings with m=199; ERA5 uses only 300 rows,
so its intervals are wide. Skill15 means skill against the recent climatology; [ ] is the 95 % interval.

| Balloons 2024-25 (B0) | skill15, known drivers | skill15, unknown drivers | MAE, recent clim -> model (unknown) |
|---|---|---|---|
| T 0-1 km | 0.028 [0.005, 0.051] | 0.018 [-0.002, 0.037] | 3.70 -> 3.61 K |
| T 1-5 km | 0.032 [0.013, 0.050] | 0.014 [-0.001, 0.029] | 2.71 -> 2.67 K |
| T 5-12 km | 0.047 [0.030, 0.065] | 0.039 [0.023, 0.054] | 2.38 -> 2.30 K |
| u 5-12 km | 0.038 [0.021, 0.053] | 0.033 [0.017, 0.047] | 9.42 -> 9.10 m/s |
| RH 5-12 km | -0.052 | -0.051 [-0.064, -0.038] | 16.8 -> 17.2 % (worse) |
| RH 12-18 km, sp, rh2m | -0.02 to -0.05 | all below 0 | worse than climatology |

The whole-profile 99 % coverage (all 44 heights inside together) is u 0.871, v 0.837, T 0.866 and RH 0.830; for
climatology it is 0.79-0.83.

What this means:
- With the honest baselines the real month-ahead skill is small: about 1-4 % better than recent climatology for T and
  upper wind.
- Most near-surface T skill was the warming trend (E1) or next-month ENSO (E2).
- RH aloft, surface pressure and rh2m are significantly worse than climatology. These are the first targets: shrink
  toward climatology, or use climatology for those columns.
- ERA5 (300-row check, wide intervals): T skill15 is 0.06-0.07 [0.02-0.03, 0.09-0.10] and u 5-18 km is 0.06-0.07.
  The full rescore of B0, A5 and slowcheck uses `--rows 5000` and replaces these numbers.
- E10 (part): sonde.py now prints the dropped count. For 2024-25, 64 of 726 (Santa Teresa) and 47 of 691 (Midland)
  00Z soundings are incomplete, about 8 %. Per-height scoring of those is still open.
- **E10 closed** (2026-11-04, E12 model, scratchpad `e10.py`, mirrors sonde.py with unknown drivers + clim15, scoring
  each cell where the balloon has data): the 111 dropped 2024-25 soundings score like the 1,306 complete ones. Skill15 is
  similar or better (u 12-18 km 0.073 vs 0.033, rh2m 0.012 vs -0.058). Coverage dips in u 0-1 km 0.970 vs 0.986 and
  RH 12-18 km 0.968 vs 0.988 (about 2 binomial standard errors at n = 111: strong winds and lost tracking are where
  balloons end early). Adding them would move pooled coverage by about 0.001, so dropping them does not flatter the
  headline; sonde.py stays as is. The complete-set numbers reproduce the official headline (RH 12-18 km 0.055 vs
  0.056), which checks the script.
- E9: `spread --drawn-drivers` (off by default) fits the map on samples with drawn drivers. Smoke-tested; queued on B0
  after the rescore (`data/e9*.log`). Keep it only if unknown-driver 99 % coverage moves closer to 0.99 without a CRPS
  loss.
- E9 result (2026-11-04, `data/e9_*.log`): **rejected, flag kept off**. Mean |unknown-driver cov99 - 0.99| over bands
  0.0029 -> 0.0028 (ERA5) and 0.0048 -> 0.0046 (balloons): no real gain; ERA5 unknown-driver skill 0.031 -> 0.029.
  The true-driver map already covers the drawn-driver case (unknown coverage was already ~0.99).
- E5: the rule is written into TOOL_PLAN (modes 3-4 refuse outside solar 06-21 h).
- Queue: slowcheck (row 21) -> rescore B0 and A5 (`data/rescore*.log`) -> E9.
- Rescore done (2026-11-04, `data/rescore_*.log`): A5 vs B0 still a tie within the day-block intervals (A5 v a bit better,
  T a bit worse); B0 stays. Weakest spot on balloons: RH 5-12 km, skill15 -0.050 [-0.063, -0.038], bias -6.3 %,
  ss_ratio 0.72, 2.6 % of truths above the 99 % range.
- E11 (found 2026-11-04): balloon-minus-ERA5 RH 5-12 km at 00Z was -5..-8 % every year 2009-2021 and -0.5..-1.9 % from
  2022 on, at both stations (a sensor or processing change). The station map fitted on 1991-2020 teaches the model the
  old balloons' drier upper air. Offline check on 2024-25 balloons (corrected ERA5 vs balloon, no model): fit 2022-23
  RH level gap 1.31 vs 2.22 (1991-2020 fit), T 0.14 vs 0.25, RH 12-18 km bias -0.4 vs +3.2; RH spread 0.96 vs 0.99.
  **E11 result: kept** (2026-11-04; `data/e11_sonde.log`, `models/generator_80_b0s2223_sonde_cal2021_headline.csv`;
  map fitted 2022-23 -> pilot80_s2223 -> B0 retrained -> 2021-23 calibration -> balloons 2024-25):
  RH 5-12 km skill15 unknown -0.050 [-0.063, -0.039] -> -0.005 [-0.021, 0.010], cov99 0.976 -> 0.994;
  RH 12-18 km skill15 -0.038 -> +0.071 [0.054, 0.088]; mean skill15 unknown -0.0007 -> 0.0069; mean |cov99 - 0.99|
  0.0048 -> 0.0040; whole-profile 99 % RH 0.827 -> 0.877. T/u/v skill within the intervals; whole-profile T 0.869 ->
  0.848, u/v unchanged. Costs: cov99 T 12-18 km 0.992 -> 0.986, t2m 0.991 -> 0.983, rh2m 0.995 -> 0.989, u 0-1 km
  0.986 -> 0.982; RH 0-1 km skill15 -0.019 -> -0.023. No ERA5 score (its targets differ by design).
  Next: a mixed-era map (RH from 2022-23, T/u/v/surface from 1991-2020) to keep the RH gain without the T/surface
  coverage cost; the full-data rebuild must use a post-2022 RH fit (pipeline3 still uses the 1991-2020 default).
  **E12: kept, replaces E11 as the balloon map** (`data/e12_sonde.log`): `models/station_map_mix.npz` = a, b and RH leftovers from 2022-23, T/u/v from 1991-2020 (RH pool
  rows cycled to the old pool size, so RH leftovers pair at random with T/u/v ones; Midland DJF groups 8-9 have no
  2022-23 balloons and keep the old fit). Same B0 recipe; compare `data/e12_sonde.log` with E11 and B0.
  E12 vs E11 vs B0 on 2024-25 balloons (skill15 unknown / cov99 unknown): RH 5-12 km -0.014 / 0.996 (E11 -0.005 /
  0.994, B0 -0.050 / 0.976); RH 12-18 km +0.056 / 0.988 (E11 +0.071 / 0.977, B0 -0.038 / 0.974); every skill gap to
  E11 is inside the intervals. Coverage cost of E11 repaired: T 12-18 km 0.991, t2m 0.989, rh2m 0.994, u 0-1 km 0.985.
  Mean skill15 0.0056 (E11 0.0069, B0 -0.0007); mean |cov99 - 0.99| 0.0034 (E11 0.0040, B0 0.0048); whole-profile
  99 % RH 0.926 (E11 0.877, B0 0.827), T 0.864, u 0.864, v 0.842. Still weak: rh2m skill15 -0.051, RH 0-1 km -0.025.
  **E13 (surface balloon map): rejected offline, not built.** rh2m skill15 on balloons is -0.051 vs +0.007 on ERA5, so
  the launch-pad vs grid surface gap was the suspect. Check (scratchpad `sfccmp.py`, 00Z, fit 1991-2020, test 2024-25):
  ERA5 rh2m already tracks the balloon surface RH (corr 0.94, bias +0.8 / +0.7 %, MAE 2.9 / 4.6 % at Santa Teresa /
  Midland); a + b * ERA5 gives MAE 2.8 / 4.8 (no gain, Midland worse). Grid and launch heights agree within 8 m. The
  negative rh2m skill is the variable's low month-ahead predictability against a sharp single-site climatology, not a
  fixable mismatch.
  2026-11-04 ~18:05: Claude Code's low-memory reaper killed the bash wrappers of pipeline3 and E12 (the E12 build held
  11 GB). Their python children kept running: E12 resumes after its build finishes; pipeline3's CDS download continues
  but its rebuild step is gone. Relaunch that rebuild after the download, with the E11/E12 winner's map, not the default.
  Done 18:3x: pipeline v4 (scratchpad `pipeline4.sh`) replaces it; identical except the station step fits 1991-2020 and
  2022-23 on profiles_bl.zarr and mixes them like E12 (`models/station_map_bl.npz`). The mix script reproduces
  `station_map_mix.npz` bit for bit.

## Phase 1 results (no retraining; E12 model; 2026-11-04/05, test years 2024-25 = development years)

Rows P1-a to P1-g follow PHASED_PLAN.md. All new behaviour sits behind flags (`--trust`, `--joint`, `--extras`,
`--stress`) and is off by default. Scores use seed 0, m = 199, 5,000 rows, drivers unknown.

**Baseline note.** Re-scoring E12 with the current code reproduces itself exactly (two runs: maximum difference 0.0),
but differs slightly from the stored E12 files (skill15 up to 0.003, MAE up to 0.07 per band), which came from an
earlier code state. All Phase 1 and later comparisons use the re-scored baseline in `models/e12_plain_new/`
(ERA5 mean skill15 +0.0273, mean |cov99 - 0.99| 0.0027; balloons +0.0071 and 0.0036). The old files are kept in
`models/e12_backup_phase1/`.

| # | What changed | Tested on | Result | Verdict |
|---|---|---|---|---|
| P1-a | Test tooling: `scripts/physics.py`, `scripts/compare_headline.py` (phase pass rule) | E12, 2024-25 | physics table reproduces A3 (99.9th shear 1-5 km: truth 25.65, calibrated 21.60; 5-12 km 30.27 vs 24.04; >12 km 34.75 vs 28.29) | kept |
| P1-b | O1 forecast logger `tempest/ops/logger.py` (WeatherNext 2 + IFS ENS, 2 sites, 13 levels + surface, validated, atomic files) | live feed 2026-11-05 | 4 files per pass (~6 MB); validator rejects truncated/short/out-of-range files (7 tests). Neither feed serves 975/950/900/800 hPa; WeatherNext has no 2 m RH or gusts. Runs as a 12 h background loop; Task Scheduler needs the user (ASK_LATER 1) | kept |
| P1-c | `profiles/thermo.py`: p, rho, speed of sound derived from T, RH, sp (decision: pressure is derived, not learned) | unit tests | isothermal column exact (1e-5); US Standard Atmosphere 1976 within 0.1 % to 18 km; spot check against ERA5/IGRA p still to do | kept |
| P1-d | Trust layer (`calibrate/trust.py`, `--trust`): rank-preserving blend toward the 15-year climatology, w per variable x band fitted on 2021-23 | ERA5 and balloons 2024-25 | v1 (blend only): ERA5 mean skill15 +0.0273 -> +0.0297 but RH coverage 0.979-0.986 (flagged worse), balloons +0.0071 -> +0.0093. v2 (blend + second range map): ERA5 +0.0293, RH 5-12 km cov99 0.9747 and RH 12-18 km 0.9673, wind 5-18 km skill15 down 0.005-0.007; balloons +0.0094, rh2m skill15 -0.049 -> -0.035, still negative. ERA5 fails rule (b) and (c) | **rejected, flag stays off** (code kept). The weak cells are low predictability, not something blending fixes |
| P1-e | Joint 99 % band (`calibrate/joint.py`, `--joint`): width multiplier per variable (u 1.43, v 1.44, T 1.46, RH 1.33) | ERA5 2024-25 | whole-profile coverage of the plain 99 % range 0.83-0.89 -> joint band 0.985-0.993 (known) / 0.985-0.992 (unknown); samples untouched | kept (output only) |
| P1-f | Extra evaluation (`scoring/extras.py`, `--extras`): PIT, coverage 50/80/90/99, wind speed and direction error, worst cells and columns; stress table (`scoring/stress.py`, `--stress`) | E12 | old columns unchanged (same-code rerun identical). Stress: weakest cells are summer T 5-12 km (cov99 0.960-0.969, n 302-537), DJF evening RH 1-5 km (0.970) | kept |
| P1-g | Coupled files (`output/coupled.py`): `atmosphere_samples.npz`, `atmosphere_coupling.npz`, TOML `[coupling]` | unit tests (3) | rows preserved, p/rho/a consistent per row, placeholders NaN, sha256 in TOML, correlations sane | kept |

Phase 1 verdict: everything kept except the trust layer. Because of the stress finding (month-dependent T 5-12 km miss),
a seasonal range map (E7) is a Phase 2 candidate, tested only if the Phase 2 retrain leaves the same weakness.

## Phase 2 results (retrain; 2026-11-04/05; development years 2024-25; baseline = E12 re-scored, ERA5 skill15 +0.0273 / cov dev 0.0027, balloons +0.0071 / 0.0036)

Datasets: `pilot80_p2.npz` (gmst, ONI hinges and lag, dpd humidity) and `pilot80_dpd.npz` (original inputs, dpd humidity), both
the same 8,000,480 rows as E12's `pilot80_smix.npz`. Training as E12 (6000 steps, 4 members) unless stated.

| # | Variant (configs/generator_*.toml) | What it contains | ERA5 skill15 / cov dev / min cov99 | Balloons skill15 / cov dev | Verdict |
|---|---|---|---|---|---|
| P2-a | p2: all flags (2.1-2.6) | dpd, gmst + hinges + lag, strides, EMA, lapse hinge | +0.0262 / 0.0036 / 0.9825 | +0.0051 / 0.0038 | **fails rule (a)**; bisected below |
| P2-b | p2a: inputs + dpd, loss flags off | 2.1, 2.2, 2.3 | +0.0262 / 0.0033 / 0.9830 | +0.0061 / 0.0039 | same skill as p2: the loss group (2.4-2.6) did not cause the drop; but T 5-18 km worse (bias 5-12 km -0.43 K -> -0.59 K) |
| P2-c | p2c: dpd only, original inputs | 2.1 | +0.0273 / 0.0029 / 0.9837 | +0.0072 / 0.0036 | **inputs (gmst, hinges) were the culprit**; dpd alone matches E12 on skill. Over-covers RH 1-5 km (0.994 vs 0.990, flagged by rule b) |
| P2-d | p2d: P2-c + shear-tail loss 0.5 | new `shear_tail_weight` | +0.0274 / 0.0030 / 0.9832 | +0.0052 / 0.0037 | extreme shear stronger (99.9th pct 1-5 km 21.5 -> 23.4) |
| P2-e | **p2e: P2-c + shear-tail loss 1.0** | `shear_tail_weight = 1.0` | **+0.0277 / 0.0032 / 0.9832** | **+0.0081 / 0.0040** | **adopted as the Phase 2 model** (`models/generator_80_p2e.pt`, calib `.calib2021.npz`, data `pilot80_dpd.npz`) |

Item verdicts:
- **2.1 dpd humidity: kept.** RH_2500 lower-tail miss 2.76 % -> 0.58 % (p2c) / 0.06 % (p2a); whole-profile RH 99 % coverage 0.852 -> 0.903 (p2a). Skill equal to E12.
- **2.2 GMST input: rejected.** Fixes the low-level cold bias (0-5 km: -0.45 / -0.35 K -> -0.18 / -0.17 K) but T 5-12 km gets colder and T/RH skill at 5-18 km drops 0.005-0.008 (P2-b vs P2-c). Flag stays off (`--features p2`, `linear_features` unchanged).
- **2.3 ONI hinges and lag: rejected** with 2.2 (confounded in P2-b; not separable without another build). Off.
- **2.4 multi-stride step CRPS: rejected.** With everything else off it made extreme shear weaker, not stronger: 99.9th pct (1-5 / 5-12 / >12 km) E12 21.6 / 24.0 / 28.3, p2 20.9 / 22.7 / 27.5 (truth 25.7 / 30.3 / 34.8). Off (`step_strides` unset).
- **2.5 EMA, 2.6 lapse hinge: not separable yet.** Only tested inside p2, which failed for other reasons; the hinge never fires on the data (no super-adiabatic samples above 2 km get penalised; unit test shows it acts when forced). Both stay off. EMA alone on top of p2e is queued (P2-f).
- **2.7 ridge smoothing of the balloon correction: rejected offline** (`scripts/ridge_check.py`): lambda 0 wins on 2021-22 (level gap 1.009, 1.010, 1.013, 1.017, 1.038 for lambda 0, 1, 10, 100, 1000) and on 2023-25. `--ridge` stays 0.
- **New: tail-weighted vector-shear loss** (`shear_tail_weight`, `shear_tail_q`): threshold-weighted CRPS of |vector shear| above its 90th percentile per layer. P2-e: 99th pct shear 1-5 km 17.9 (truth 17.9), 5-12 km 19.7 (20.7), >12 km 23.9 (25.1); 99.9th pct 23.5 / 26.2 / 30.3 (truth 25.7 / 30.3 / 34.8; E12 21.6 / 24.0 / 28.3). Cost: 0-1 km 99.9th pct 82.3 truth, E12 79.6, P2-e 76.9. Kept (weight 1.0).
- Training time with strides + EMA was 23 min (over the 15 min guideline); p2c/p2d/p2e train in 14-15 min.
- Noise: training-to-training variation is being measured with a second seed of P2-c (P2-g, running); until then differences below about 0.003 in a single cell are not conclusive.
- Note on rule (b): in every variant that includes 2.1 the ERA5 cell RH 1-5 km is flagged because it is over-covered (0.994-0.995, target 0.990), not under-covered. Mean |cov99 - 0.99| stays 0.0029-0.0032 and the lowest band 0.983. Not repaired; candidate for the improvement loop (refit range calibration after dpd).

**P2-g (training noise).** P2-c retrained with seed 1 (`generator_p2cs1`): mean skill15 ERA5 +0.0263 vs +0.0273 (seed 0), balloons +0.0052 vs +0.0072;
per-cell skill15 differences between the two seeds: mean 0.0013 / 0.0026, maximum 0.0041 / 0.0094 (ERA5 / balloons); mean
|cov99 - 0.99| 0.0030 vs 0.0029 (ERA5), 0.0035 vs 0.0036 (balloons). **Consequence:** a change in mean skill15 below about 0.002
(ERA5) or 0.003 (balloons), or in a single cell below about 0.005 (balloons 0.01), cannot be told from a retraining. All
Phase 2 skill differences between P2-c, P2-d and P2-e are inside this noise; only the shear percentiles (which moved by
2-3 m/s per km, far outside seed variation of the physics check) and the RH tail are real effects. Future decisions on
skill need either a larger margin or several seeds.

## Phase 3 results (new modules and data; 2026-11-05; development years 2024-25 unless stated)

Data note: the Earthmover store (`single/temporal`, `pressure/temporal`) holds gusts (`fg10`), boundary-layer height (`blh`), solar radiation
(`ssrd`, `ssr`), latent heat flux (`slhf`) and vertical velocity (`w`, omega), so no CDS queue was needed except for `sshf` (sensible heat flux), which
the store lacks (ASK_LATER 5). Pulled with `fetch_earthmover --only ...` (about 6 minutes in total); airport reports from the Iowa Mesonet
(`fetch_asos`, MAF and TCS, 2000-2025).

| # | Item | Test and numbers | Verdict |
|---|---|---|---|
| P3-1 | Gust module (`tempest/gust/`, `scripts/gust_check.py`): Gumbel regression on peak gust, inputs = model 10 m wind + season + hour + station (+ ERA5 fg10) | fit 2000-2020 (364k hourly reports), test 2024-25 (34k): CRPS 1.40 [1.36, 1.44] m/s vs 2.11 (bias-corrected fg10) and 2.21 (constant factor 1.48); 90 % range holds 0.890, 99 % holds 0.986; ERA5's own gust field adds nothing (1.395 vs 1.402). First version (reported-gust mixture bounded below by the model wind) held the 99 % range only 59 % of the time: dropped | **kept** (module off until the tool uses it) |
| P3-2 | Vertical wind: a w-head (`tempest/output/whead.py`, `scripts/whead.py`, `build_wdata.py`), an Engression network conditioned on the sampled atmosphere, instead of 44 extra outputs of the main generator (223-output retrain) | data: omega -> w m/s via `thermo` on 8,000,480 rows (75.6 % have w; ERA5 w starts 1990-10-29); eval with m = 199 generated atmospheres per row: skill vs 15-yr climatology +0.0094 [0.0015, 0.0165] at 1-5 km, +0.0141 [0.0081, 0.0201] at 5-12 km, +0.0108 [0.0055, 0.0162] at 12-18 km, -0.0031 [-0.0160, 0.0077] at 0-1 km; 99 % range holds 0.984-0.989; spread/skill 0.91-0.94 (slightly narrow) | **kept** (deviation from the written plan: keeps the passed generator untouched; the Monte Carlo coupling is kept because w is drawn given the sample) |
| P3-3 | Thermals (`tempest/output/thermals.py`): w*, Lenschow sigma_w, skewed height-coupled draws | 4 physics unit tests. The spec's sigma_w formula drops a square root (would be 34 % too strong); the variance form is used. **Not data-checked**: needs sshf and 1-second soundings (ASK_LATER 5) | built, **off**; check blocked |
| P3-4 | Soak history (`profiles/surface_hourly.py`, `output/soak.py`, `scripts/soak_check.py`) | 800 test rows, final model p2e: overnight-minimum CRPS 1.875 [1.755, 2.003] K matched vs 2.063 [1.963, 2.177] unmatched; T_soak (tau 3/6/12 h) CRPS 2.20 / 2.08 / 2.03 matched vs 2.23 / 2.14 / 2.10; 90 % ranges hold 0.915-0.929 (target 0.90), 99 % ranges 0.993-0.996 | **kept** |
| P3-5 | Longer record 1980-2023 with gmst + ONI-hinge inputs + shear loss (`generator_p35`, dataset `pilot80_p2`, train `--min-year 1980`) | ERA5 skill15 +0.0277 / cov dev 0.0031 / min cov99 0.9828; balloons +0.0082 / 0.0032 (P2-f: +0.0277 / 0.0034; +0.0083 / 0.0039): no difference in skill. T bias (ERA5, K) 0-1 / 1-5 / 5-12 / 12-18 km: -0.52 / -0.47 / **-0.70** / 0.00 vs P2-f -0.46 / -0.36 / -0.44 / +0.02 | **rejected**: a 10-year longer record with the global-temperature input does not remove the cold bias, it deepens the one at 5-12 km. P2-f stays |
| P3-6 | More IGRA stations | IGRA list checked: no other station inside the box 31-34 N, 108-101 W; nearest Albuquerque and Amarillo (1.0-1.2 deg north), Del Rio (1.6 S), Tucson (1.5 W) | **blocked by geometry**; needs a larger ERA5 box (CONUS stage) |
| P3-7 | Index forecast bake-off (`scripts/index_bakeoff.py`, `ingest/index_forecast.py`) | 2012-2025 hindcasts, horizons 1-12 months, mean CRPS over horizons: ONI regression 0.342 vs analog K=8 0.424 vs climatology 0.457 vs persistence 0.636; QBO30 4.63 vs 5.91 vs 9.12; QBO50 2.75 vs 3.35 vs 4.89; WWV regression also best. At 12 months ONI regression 0.470 vs climatology 0.478 (skill gone). Chronos-2, CPC/IRI/NMME not run (ASK_LATER 6) | **regression kept** as the index forecast for the tool (joint draws); the analog draw stays the scoring default so numbers stay comparable |
| P3-8 | Coupled file filled in (`coupled.build(extras=...)`) | placeholders replaced row for row; `w` joins the correlations; unit test. Coupling accuracy check (`scripts/coupling_check.py`, p2e, Midland June 17 h, 2000 real vs 600 generated): mean |difference of correlation| 0.046-0.053 per height band (sampling noise 0.021-0.025), vertical u/v/T/RH 0.038/0.055/0.033/0.061; shear 99 / 99.9 pct real 27.5 / 51.4, generated 26.7 / 52.6 | **kept**; coupling about twice the sampling noise off, not exact |
| P3-9 | Launch-commit P(scrub) | needs the user's go/no-go limits | **blocked** (ASK_LATER 3) |

### End-of-phase checklist (Phases 1-3), 2026-11-05
- Phase 1: 1.0 tooling, 1.1 logger, 1.2 thermo, 1.3 trust (rejected, off), 1.4 joint band, 1.5 extras, 1.6 stress, 1.7 coupled files: all built, tested, logged (rows P1-a to P1-g). Gap found and closed: the coupled-file accuracy test (tests 1-2) is now `scripts/coupling_check.py` (row P3-8).
- Phase 2: 2.1 kept; 2.2, 2.3, 2.4, 2.7 rejected; 2.5 EMA alone is running (P2-f); 2.6 lapse hinge off (never fires on the data); new shear-tail loss kept.
- Phase 3: 3.1, 3.2, 3.4, 3.7, 3.8 built and tested; 3.3 built, data check blocked; 3.5 pending; 3.6 and 3.9 blocked with reasons above.

**P2-f (EMA alone on top of P2-e; `generator_p2f`).** Weight averaging, decay 0.999, evaluated and saved instead of the raw weights. ERA5 skill15 +0.0277 / cov dev 0.0034 / min cov99 0.9832;
balloons +0.0083 / 0.0039 (P2-e: +0.0277 / 0.0032; +0.0081 / 0.0040, so skill is unchanged). Shear percentiles (m/s per km; truth in brackets): 99th 18.3 (17.9) / 20.4 (20.7) / 25.5 (25.1) at 1-5 / 5-12 / >12 km,
99.9th 24.0 (25.7) / 27.1 (30.3) / 32.5 (34.8), against P2-e 23.5 / 26.2 / 30.3 and E12 21.6 / 24.0 / 28.3; 0-1 km 99.9th 77.8 (82.3; E12 79.6). Training 15.6 min.
**Kept: the Phase 2 model is now `models/generator_80_p2f.pt`** (calibration `generator_80_p2f.calib2021.npz`, data `data/train/pilot80_dpd.npz`, config `configs/generator_p2f.toml` =
`generator.toml` + `shear_tail_weight = 1.0` + `ema_decay = 0.999`; humidity learned as dewpoint depression via the dataset's `rh_target = dpd`). 2.5 (EMA) is therefore kept; 2.6 (lapse hinge) stays off.

**P3-8 end-to-end check (`tempest/output/atmosphere.py`, `out/demo_spaceport`).** One call from (32.99 N, 106.97 W, 2027-06-16 15:00 solar) builds 1,024 coupled atmospheres with the Phase 2 model p2f: indices from the
ridge forecast (9 months ahead), range-calibrated samples, vertical wind from the w-head, 10 m gust parameters, 24 h soak history, written as the three coupled files. June afternoon values are
plausible: t2m 306.9 K (sd 3.6), surface pressure 848 hPa, air density 0.96 kg/m3, 10 m wind mean 5.1 / 99th pct 11.2 m/s, gust location 5.3 m/s + scale 2.2 (mean gust about 6.5 m/s),
w at 1 km sd 3.1 cm/s, T_soak (tau 6 h) 302.8 K, 24 h t2m range 14 K. Still NaN: `w_sigma`, `w_turb` (needs sshf), gust parameters above 10 m.

## Phase 5 results (the tool, `tempest_weather/`; 2026-11-05; plan: Code-Modifications/PHASE5_TOOL.md)

| # | Step | What exists and what was measured | Verdict |
|---|---|---|---|
| P5-1 | Exporter + numpy engine | `tempest/export_tool.py` writes `assets/` (generator 4 members, calibration, w-head, gust model, past-date network, index snapshot, grid, manifest with sha256; 75 MB, not in git). `engine.py` is a torch-free forward pass: same weights and noise reproduce the torch samples within 2e-4 relative (`tests/test_tool_parity.py`); copied numerics (humidity rule, thermodynamics, range calibration) match their originals | kept |
| P5-2 | Distributions and coupling | six types, one file each (normal, lognormal, gumbel, weibull, beta, empirical), selection rule with a tail check and empirical fallback; coupling: `whole_sample` (rows of real atmospheres, optional stratified draws) and `gaussian_copula` (rank correlations + marginals, limits documented); 10 tests incl. parameter recovery | kept |
| P5-3 | Ranking, outputs, the four calls, terminal command | `values`, `distribution` (settings 0-3), `couple`, `atmosphere` (percentiles along a worst-to-best flight-condition order; default 15/50/85; simulator-ready text / TOML in the `dynamics` layout / json); `python -m tempest_weather atmosphere|values|variables`; 11 API tests. Flight-score weights are placeholders for the user's limits | kept |
| P5-4 | Modes | `ai` works everywhere in the pilot box; `past` works with a local ERA5 store (ERA5 + learned correction + calibrated range, or the bare ERA5 value without model error; test: spread of T at 5 km is under half the climate model's spread); `recent`, `week`, `medium` fall back to `ai` with `fallback-mode` flagged (no verified source yet) | partly: 2 of 5 modes live |
| P5-5 | Standalone and operations | README; numpy-only run from a scratch copy with pandas/torch/xarray/scipy/tempest blocked (test); manifest hash refusal (test); `tempest/ops/health.py` (archive freshness and gaps, asset hashes; real archive: OK) | kept |
| P5-6 | Flight-sim readers (C3/C4) | `tempest_weather/flight_sim_readers.py`: `TempestWind` (velocity in the sim's (up, east, north) world frame) and `TempestAtmosphere` (temperature linear, pressure log-linear, density and speed of sound recomputed, standard-atmosphere tail above 18 km, launch-elevation anchor check), duck-typed to `WindModel` / `AtmosphereModel`; 3 tests (exact at grid heights, ideal-gas consistency between them, rules above/below, same sample index). Coupled files carry `stratum_key` for the one-dimension LHS (EDITH side not touched: needs agreement with its owner). The landing-scatter end-to-end test (C6) needs a vehicle file and the sim: not run | partly |
| P5-7 | Validation | `scripts/tool_validate.py`: 1,000 held-out 2024-25 rows through the TOOL's numpy engine against ERA5: 99 % range coverage 0.985-0.997, mean abs distance from 0.99 = 0.0026; the main scorer's coverage lies inside the tool's 95 % interval in 17 of 19 cells | kept |

### Final state of the Phase 3 checklist (2026-11-05)
3.1 gust built and kept; 3.2 vertical wind built (as a conditional head) and kept; 3.3 thermals built, data check blocked (ASK_LATER 5); 3.4 soak kept; 3.5 run and rejected; 3.6 blocked by geometry;
3.7 index forecast kept; 3.8 coupled files filled and end-to-end demo (`tempest/output/atmosphere.py`) plus the tool; 3.9 blocked on the user's limits. Every kept item has a test and a row above.

## Improvement loop (after Phase 5; each row: one change, tested on the development years 2024-25 unless stated; noise level: training-to-training about 0.002 mean skill15)

| # | Change | Result | Verdict |
|---|---|---|---|
| IL-1 | Past-date network (mode P) gets ERA5 one hour after launch minus ERA5 at launch as extra inputs (`p4_modeP.py --tendency`; a balloon climbs ~90 min) | hybrid mean MAE vs balloons 2.571 -> 2.561, CRPS 1.867 -> 1.864 (0.4 %); wind aloft 1-2 % better, RH 0-1 km worse (+0.15 %) ; inside the noise | rejected (flag off) |

| IL-2 | Seasonal width factors (month x variable-band) on top of the range map; flag `score --seasonal`, off by default | Fit 2021-23, test 2024-25 (ERA5, seed 0, m=199): mean skill15 +0.0277 -> +0.0277 (rule a fails on rounding); mean abs(cov99-0.99) 0.0034 -> 0.0019, 4 bands closer (RH, rh2m) with intervals apart; but the target cell T 5-12 km got worse (0.9832 -> 0.9805) because the fitted summer factors there are ~1.00 (the 2021-23 summers do not show the miss) and the fit mostly shrinks. No balloon check (sonde has no --seasonal). | Not adopted, flag stays off. Coverage gain is real but is overshoot trimming, not the weak summer-T cell; revisit only with a fit on a longer calibration window (needs walk-forward folds). |

| E4-f2 | Walk-forward fold 2 (train <=2020, calibrate 2018-20, test 2021-23), E12 baseline vs adopted p2f | Wind and temperature (clean): ERA5 skill15 within +-0.002 in every band (tie); balloons wind +0.001..+0.006 (v 5-12 km +0.006), T 5-12 km -0.005. Mean skill15 ERA5 +0.0170 vs +0.0168 (rule a fails by 0.0002, noise), balloons +0.0076 vs +0.0084. Mean abs(cov99-0.99) 0.0059 -> 0.0036 ERA5, 0.0040 -> 0.0038 balloons; RH 12-18 km cov99 0.952 -> 0.983. RH numbers contaminated (station map RH part fitted on 2022-23). | p2f is no worse than E12 on a second period; its gain is calibration (humidity, shear tail), not mean skill. Adopted status stands. |

| IL-4 | Read the Earth-GRAM 2026 User Guide (NASA/TM-2026-0004497, May 2026) for ideas worth absorbing | Useful: (1) patchy severe turbulence: variance split into a rare "severe" regime (variance x6..x12, shorter vertical scale) and a calm one, switched by an auto-correlated hidden scale; this is what keeps its shear tail heavy. Our 99.9th-percentile shear is still ~6-20 % low (24.0/27.1/32.5 vs truth 25.7/30.3/34.8), so a tail layer for the shear columns (GPD or regime mixture, off by default) is the one idea to test. (2) Hourly time correlation exp(-dt/tau) between consecutive profiles (CorrMonte); we already have soak sequences, so only a check that our hour-to-hour correlation matches balloon/ERA5 pairs. (3) Boundary-layer vertical-wind sigma_w = 1.25 u* (1 - 3z/L)^(1/3) from stability and roughness; we have Lenschow thermals and a learned w head, compare only. Not useful: its data are MERRA-2/NCEP, global zonal tables, 20-200 km upper atmosphere. | Idea (1) queued as IL-5; (2),(3) are checks. No code change from reading. |

| IL-6 | Look for lead-time forecast history other than the logger (earlier probe covered Open-Meteo only) | Found public, anonymous, no-login archives: WeatherBench2 on Google Cloud (`gs://weatherbench2/datasets/`, read over https): `hres` = IFS HRES forecasts, 2016-01 to 2023-01, 12-hourly starts, 6-hourly leads 0-10 days, 0.25 deg, 13 pressure levels (u, v, T, q, z, w) plus 10 m, 2 m, surface pressure; `ifs_ens` = IFS ensemble, 50 members, 2016-2024, leads 0-15 days, but only 500/700/850 hPa; `ifs_extended_range` (weeks 3-6, structure still to open); also GraphCast, Pangu, GenCast, FuXi, NeuralGCM forecasts. NOAA GFS on AWS (`noaa-gfs-bdp-pds`, with .idx byte-range files, all leads, 2021 on). TIGGE via the CDS key is a further option. This covers 2016-2022 (train + calibrate) and 2021-2024 for IFS ENS, so modes F/F2 can be calibrated on real lead-time history now instead of waiting a year for the logger. Needs aiohttp/requests/fsspec in the venv (probe ran with a temporary copy outside the repo). | Queued after IL-3/IL-5: box subset fetch (HRES first), then calibrate modes F/F2 on 2016-2020, verify 2021-22, test 2024 with IFS ENS where it overlaps. The logger keeps running for the live feed and for providers not archived. |

| IL-7 | What to take from the Chronos-2 architecture (read from the code in `chronos/chronos2/{model,layers}.py` and `config.json`) | Chronos-2 is a T5-style encoder only (12 layers, width 768, 12 heads, ~120 M parameters). Series are cut into 16-step patches; each token = [time encoding, patch values, observed-mask]; per-series instance normalisation with arcsinh; a register token; rotary positions. Every block alternates TIME self-attention (along one series) and GROUP self-attention (across the series of one group, with no order: targets, past covariates and known-future covariates all sit in the group), so the model learns cross-variable links in context without per-task training. It emits 21 quantiles for 64 patches in one pass (no autoregression). Pretrained on synthetic series. Transferable ideas, in order of expected value: (a) a height-token generator: tokens = the 44 heights (4 variables each) with attention along height, replacing the flat MLP, to model vertical structure and shear (our 2B/2C/3B family) - IL-8; (b) mask tokens for missing inputs with random input dropout, so the tool answers sensibly when a driver or station is missing (generalises the known/unknown-driver split) - IL-9; (c) arcsinh instance scaling for heavy-tailed targets (shear, gust) - cheap check in IL-9; (d) use the pretrained model as is for the ONI/WWV/QBO forecast (running now, scripts/chronos_bakeoff.py) and, if it wins, for weekly anomaly forecasts with covariates in mode M. Not transferable: direct quantile outputs (we need joint samples), the 120 M-parameter size (35 years of one box would overfit). | Expectation stated honestly: skill is limited by predictability, not architecture; a transformer is a level-3 bet worth one attempt, not a drastic improvement. |
