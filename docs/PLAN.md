# Tempest-ARKNET plan (v2)

Weather for **Monte Carlo flight simulation** at any place in the contiguous US, any day, 08:00–20:00
local time, from tomorrow to about three years ahead. Past dates are handled too.

Status: planning. Nothing is built yet. The flight sim (FS / JARVIS, in the `dynamics` repo) is **not**
changed by this work; its side comes later.

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
        MLP, 5 layers × 512, about 0.9 M parameters  (tempest/generator/, configs/generator.toml)
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
  (as AIFS-CRPS / DeepMind FGN), ~2.8 M parameters. 4 independently trained seeds are pooled at sampling
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
| 21 | training speed: the 4 members train side by side in one loop (training rows normalised once and kept on the GPU in float16, forward pass in bfloat16, fused AdamW), `steps` 20000 -> 6000 to fit a 15-minute budget | timing on pilot_st.npz; accuracy: B0 of A5 (6000 steps) vs B0 retrained with `configs/generator_slow.toml` (20000 steps), same data and split, ERA5 + balloons 2024-25 | **pending accuracy check** (runs after A5). Speed measured: 4-member step 125 ms (was ~208 ms one member after another), so ~13 min for 6000 steps; 20000 steps would still take ~42 min because the GPU is now full (torch.compile is not available here: no Triton on Windows). The 6000-step cut is reverted if the 20000-step model is clearly better. |
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
- E9: `spread --drawn-drivers` (off by default) fits the map on samples with drawn drivers. Smoke-tested; queued on B0
  after the rescore (`data/e9*.log`). Keep it only if unknown-driver 99 % coverage moves closer to 0.99 without a CRPS
  loss.
- E5: the rule is written into TOOL_PLAN (modes 3-4 refuse outside solar 06-21 h).
- Queue: slowcheck (row 21) -> rescore B0 and A5 (`data/rescore*.log`) -> E9.
