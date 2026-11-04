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
        ─ surface T, p, RH, 10 m wind
            │
            ▼
        sum the differences up from the surface → 44-level profile
```

- **Why Engression** (arXiv 2307.00835): the noise goes in before the network, not after it. That lets the
  model extrapolate a little beyond its training range, which matters because 2027–2029 are warmer than
  every training year. DExtrI (2608.19849) is the follow-up for interactions between drivers.
- **Loss:** energy score on the whole output vector. It is a proper score, so the model is rewarded for the
  right spread and joint shape, not just the right mean, and because the outputs *are* the neighbour
  differences, it scores the shear directly. The variogram score is used for evaluation (phase 2 harness),
  not in the loss: estimating it from 4 samples per row is too noisy.
- **Training targets:** ERA5 profiles after the station correction. The generator learns balloon-like shear
  and spread, not ERA5's smoothness. Pilot: S4's quantile map (both sites have a nearby IGRA station).
  CONUS: **option 3C** (a learned ERA5 → radiosonde correction conditioned on terrain and site) carries
  the correction to points far from any station, and 3A is retrained on its output (decided 2026-11-04).
- **Training data:** pilot box first, then CONUS samples drawn from the store on the fly (phase 8).
  Measured 2026-11-04 on this machine's RTX 5070 Laptop GPU (12 GB) at pilot size (400k rows, 13 inputs,
  181 outputs): 17–30 ms per step at batch 4,096, 0.4 GB GPU memory, so a 20,000-step run takes about
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
Sizing for CONUS (≈ 13k points, 35 years, solar 06–21 h, 44 heights × 4 variables + 5 surface = 181 values,
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
2. **CDS fill not merged yet** (`to_heights.open_raw` stops if gribs exist). Boundary layer uses 13 levels only.
3. **Year feature extrapolates** past 2025. Query outside the training range should fall back to analogs (G F22).
4. **WWV/ONI at query time are forecasts**, training uses observed values: leakage. Train with lagged or
   forecast-like values, or add noise (G C9, C #4).
5. **m = 4 samples per row** may under-spread; check PIT per height after the first run, try m = 8 (G F18).
6. **Loss weights every target equally**: 44 wind heights outweigh 3 surface values. Check per-variable
   scores before reweighting (G F19).
7. **Rows are correlated** (neighbouring hours/points): validate by whole years, never random rows (C #10).
   Already done: last 3 years held out.
8. **Physics checks**: hydrostatic height test (G A5), shear at 99th percentile vs IGRA (G F20).
9. **Scale**: the npz is held in RAM. Fine for the pilot (~6 GB); CONUS needs streaming.
10. **IGRA host (NCEI) was down** on 2026-11-04; rerun `fetch_igra` later.
