# Tempest-ARKNET — Comprehensive Experiments Ledger (`EXPERIMENTS_LEDGER.md`)

> **Ordering Convention:** Strictly ranked from **MOST BENEFICIAL (Tier 1 Shipped Defaults — deepest intuitive & technical detail at top)** down to **UNSUCCESSFUL / REJECTED / NEGATIVE IMPACT (Tier 4 Post-Mortems at bottom)**. Every experiment begins with a plain-English conceptual explanation and analogy before presenting exact technical mechanics, verbatim benchmark numbers, and code references. All metrics and experiment IDs are sourced verbatim from the repository logs (`docs/results/FINAL_REPORT.md`, `docs/results/APPLIED_STATUS.md`, `docs/logs/SIDELINED.md`, `docs/plans/PLAN.md`, `Useful results.md`, `New_Plan.md`, `docs/logs/AUTOPILOT.md`, and `FlightSIM&Validation with Tempest-ARKNET.md`).

---

## Executive Summary & Judging Rules

> **How to Read These Benchmarks (Plain English):** Every experiment in this ledger is graded on three everyday questions. **CRPS skill** asks how much sharper and closer to reality our 400 generated skies are than simply guessing the 15-year seasonal average (positive = better). **99% coverage (`cov99`)** checks whether real weather actually lands inside our outer safety bounds 99% of the time—like verifying a rocket range safety net. **Seed noise** is the tiny random wobble from re-running training with different random numbers; any change smaller than that wobble counts as a tie, not a real win.

### How Experiments Were Judged

Every candidate change in Tempest-ARKNET had to clear a two-part statistical gate (`docs/results/APPLIED_STATUS.md`) before adoption:

1. **Headline Accuracy & Coverage (`scripts/compare_headline.py`):** Evaluates `skill15` (CRPS skill relative to a 15-year recent climatology across 19 variable × height-band cells) and `cov99` (mean distance of the 99% ensemble range from 0.99 coverage) with date-block bootstrap confidence intervals on both ERA5-type targets and independent IGRA2 radiosonde balloons (Santa Teresa `EPZ` / `72364` and Midland `MAF` / `72265`).
2. **Whole-Distribution Shape Fidelity (`scripts/compare_shape.py` via `shape_verdict.sh`):** Measures 8 shape diagnostics — Probability Integral Transform (PIT) distance from flat (`pit_tv`), per-level coverage error (`cov_err_mean`), skewness difference (`skew_diff`), kurtosis difference (`kurt_diff`), tail-rate error (`tail_rate_err`), event-conditional coverage gap (`event_cov_gap`), vertical correlation error (`vcorr_err`), and wind-shear Kolmogorov–Smirnov distance (`shear_ks`). A metric is flagged **WORSE** if it degrades by more than the empirical seed-to-seed spread of three seeds of `p2f` (floored at 2%).
3. **Pass Rule:** A real gain requires `skill15` (or a targeted shape metric) to improve by more than the seed-noise yardstick, with **nothing flagged WORSE** in either headline or shape tests.

### Seed-to-Seed Noise Yardstick & Audit Hygiene

- **Empirical Seed Noise (`IL-92`, `p2f` across 3 training seeds):** ERA5 `skill15` spread = **0.0006** (`+0.0277 / +0.0271 / +0.0276`); IGRA2 balloon `skill15` spread = **0.0013** (`+0.0084 / +0.0073 / +0.0071`); `|cov99 - 0.99|` spread = **0.0004** (ERA5) and **0.0003** (balloons). Later `c4w` multi-seed checks confirmed mean `skill15` moves by ~**0.0005** between training seeds and single bands by up to **0.003**.
- **Fair Baseline Audit (`AU-1`):** Plain CRPS penalized the finite 15-year climatology pool (`R ≈ 75` draws) by ~**+0.013** on ERA5 (`+0.003` on balloons). Enabling `--fair-baseline` (Ferro 2014 fair CRPS over the full pool without replacement) adjusted the honest ERA5 `skill15` (unknown drivers) from `+0.030` to **+0.017–0.018** (`+0.007` on balloons), while leaving model-vs-model differences unchanged.
- **21-Day Block Bootstrap (`AU-4`):** Daily CRPS error autocorrelation decays within 1–7 days for most bands but persists to 19 days for `T 12–18 km`. Upgrading `tempest/scoring/diag.py` from 1-day to **21-day blocks** (`BLOCK_DAYS = 21`) widened confidence intervals by median **1.60×** (up to **2.0–2.6×** at `T 12–18 km`).

### Data Hygiene: 2024–25 Development vs. Untouched 2026 Jan–Jun Final Test

| Split | Period | Role | Key Benchmark Summary |
|---|---|---|---|
| **Training** | 1991–2020 | Generator weights & station maps | 8,000,480 pilot rows (`0.25°`, 377 grid points) |
| **Validation / Calibration** | 2021–2023 | Early stopping, spread maps, shear/lapse maps, shuffle templates | Never used for final claims |
| **Development Test** | 2024–2025 | Iterative accept/reject decisions (30+ experiments; slightly optimistic) | ERA5 `skill15` **+0.0278** (plain) / **+0.017–0.018** (fair); balloons **+0.0084** (plain) / **+0.007** (fair) |
| **Untouched Final Holdout** | **2026 Jan–Jun** | Run **once** (`scripts/final_test.sh`, lock file, zero tuning) | ERA5 `skill15` **+0.0209** (E12 +0.0204), `|cov99-0.99|` **0.0049**, vs Gaussian **+5.6%** (13/19 cells); Balloons `skill15` **+0.0187** (E12 +0.0160), `|cov99-0.99|` **0.0064**, vs Gaussian **+2.2%** (12/19 cells) |
| **Reserved Second Holdout** | 2026 Jul–Oct | Downloaded & locked (`final_test_2026h2.sh`) | Held untouched for post-freeze final verification |

### Flight-Simulator Validation Summary (`FlightSIM&Validation with Tempest-ARKNET.md`)

Only **3 of 38** flights in the `JARVIS-TRUE-VALIDATION` benchmark launched inside the trained NM/TX pilot box (Spaceport America, NM): **Prometheus** (2022-06-24, truth 12,789 ft), **Juno III** (2023-06-23, truth 10,541 ft), and **Heart of Steel** (2017-06-22, truth 30,411 ft).
- **Real Air vs. Real Wind:** Real hot desert air (26–37 °C vs. 6 °C ISA at 1,401 m, density 0.96–1.00 vs. 1.07 kg/m³) raises simulated apogee by **+1.5 to +3.1%**, while real wind (8–19 m/s) lowers it by **~2%** via rail weathercocking (87% of wind-driven apogee spread comes from **0–300 m**, 53% from **50–150 m** alone).
- **Vehicle Error Dominates Apogee:** All three simulators (FS, RASAero II, RocketPy) over-predict Prometheus and Juno III by **+5 to +8%** due to drag, mass, impulse, and rail-guide errors — **2–4× larger** than the atmospheric signal. Consequently, atmosphere-only ensembles must be paired with `VehiclePriors` (`tempest_weather_v2/montecarlo.py`), and the **hybrid `air="standard"` + Tempest wind** option achieved the lowest 3-flight MAE (**4.89%** vs. 6.15% standard air, 5.80% full Tempest past, 5.21% branch as filed) by partially cancelling simulator over-prediction.

---

## Tier 1: Major Adopted Wins (Shipped Defaults — Deepest Detail)

These 13 breakthroughs form the production backbone of Tempest-ARKNET (`tempest/`, `tempest_weather/`, and `tempest_weather_v2/`).

---

### 1.1 Dewpoint Depression Coordinate (`dpd`) + Tail-Weighted Shear Loss + EMA (`p2f`)

- **Concept & Intuition:** Relative humidity (RH) is a notoriously awkward variable for a neural network because it hits hard walls at 0% and 100% — like trying to throw darts at a board glued to a brick wall, where normal noise constantly bounces out of bounds and gets clipped flat.
  - Switching the humidity target to **log dewpoint depression** — how many degrees cooler the air would need to get before fog forms, compressed logarithmically — turns that walled box into an open, smooth hillside so the network naturally respects saturation without smashing into 0% or 100%. Pairing that with a **tail-weighted shear loss** is like telling a weather trainee: *"Don't just get calm breezes right on average — pay extra attention whenever the wind changes violently with altitude (the top 10% of shear events), because those are the gusts that snap rocket fins."* Finally, **EMA (Exponential Moving Average)** smooths the network's weights over the last training steps, like averaging a shaky photographer's hand to get a crisp exposure.
- **Technical Implementation:**
  - Replaced raw RH (%) with `lnd = ln(1 + max(T - Td, 0))` (`--rh-target dpd`, `tempest/generator/sample.py::dpd_from_rh`, `rh_from_dpd`).
  - Added `shear_tail_loss()` (`tempest/generator/train.py`, `shear_tail_weight = 1.0`, `shear_tail_q = 0.9`): applies `afCRPS` to `ReLU(S_l - q_{0.9,l}) / sigma_excess_l` where `S_l = sqrt(du^2 + dv^2) / dz_km`.
  - Enabled weight EMA (`ema_decay = 0.999`) in `configs/generator_p2f.toml` (`models/generator_80_p2f.pt`).
- **Exact Quantitative Gains (2024–25 Dev vs. E12 Baseline):**
  - **Humidity Tails (`dpd`):** `RH_2500` lower-tail miss dropped from **2.76% → 0.58%** (`p2c`) / **0.06%** (`p2a`); whole-profile RH 99% coverage rose from **0.852 → 0.903**.
  - **Extreme Wind Shear (m/s per km, 99.9th percentile vs. truth `[25.7, 30.3, 34.8]`):** Lifted from E12's `21.6 / 24.0 / 28.3` to **`p2f`'s `24.0 / 27.1 / 32.5`** across `1–5 / 5–12 / >12 km`; 99th percentiles hit **`18.3 / 20.4 / 25.5`** vs. truth `17.9 / 20.7 / 25.1`.
  - **Headline Skill:** ERA5 `skill15` **+0.0277** (E12 `+0.0273`), Balloons `skill15` **+0.0083** (E12 `+0.0071`); 15.6 min training time.
- **Code & Config:** `tempest/generator/sample.py`, `tempest/generator/train.py::shear_tail_loss`, `configs/generator_p2f.toml`.

---

### 1.2 Near-Ground Vector Wind Loss (`c4w`)

- **Concept & Intuition:** Standard atmospheric loss functions treat every altitude equally from 10 m up to 18 km — meaning the lowest 300 meters (where a rocket leaves the launch rail slowly and weathercocks into the wind) is just a tiny sliver of the training penalty.
  - Even worse, scoring East-West (`u`) and North-South (`v`) wind separately lets the model miss the true wind speed magnitude. `c4w` adds a dedicated **near-ground vector-wind spotlight** on the lowest 300 meters, training the network specifically on the combined 2D wind vector right where rockets are most vulnerable.
- **Technical Implementation:** Added `low_wind_loss()` (`wind_vec_weight = 0.5`, `low_top_m = 300.0`) on top of the `p2f` recipe (`configs/generator_c4w.toml`, `generator_80_c4w`), with its own refit spread calibration, shear map, and lapse map.
- **Exact Quantitative Gains (2024–25 Dev vs. Shipped `p2f` + Lapse Map):**
  - **Headline Skill:** Mean `skill15` improved by **+0.0013 / +0.0016 / +0.0013** across score seeds 0–2, and **+0.0024** on a second independent training seed (3–5× the 0.0005 seed-noise yardstick).
  - **Per-Band & Coverage:** Better RH and **0–1 km wind** skill, plus lower overall coverage error.
  - **Scope Limit:** Strictly in-box — zero-shot in Denver it degrades temperature transfer on both training seeds, so Denver uses its own locally trained model.
- **Code & Config:** `tempest/generator/train.py::low_wind_loss`, `configs/generator_c4w.toml`.

---

### 1.3 All-24-Hour Training (`l3_c4w`) + Denver Local Models (`l3_blocal_c4w` / `a24den_c4w`)

- **Concept & Intuition:** Earlier versions of Tempest-ARKNET were like a daytime-only weather observer who went home at sunset — refusing any query outside 06–21 local solar time and stumbling badly (`-0.021` skill) when asked to extrapolate into early-morning 12Z balloon launches.
  - Similarly, Denver was previously served by an underpowered small model that performed *worse* than simply guessing historical averages (`-0.115`). Retraining the `c4w` architecture on **all 24 hours of 21-level ERA5 data** taught the network the full diurnal cycle (nocturnal inversions, dawn calm, afternoon mixing), while training dedicated local Denver models replaced the broken Denver bundle with a properly calibrated regional system.
- **Technical Implementation:**
  - Shipped NM/TX bundle (`assets`): `l3_c4w` (all 24 h, 21-level ERA5, with 2° shuffle templates, shear map, lapse map, and all-hours `whead_a24`).
  - Shipped Denver bundles: `assets_denver` (`l3_blocal_c4w`, 06–21 h) and `assets_denver_allhours` (`a24den_c4w`, outside 06–21 h), both with full post-processing (`IL-170 / D-1`), Denver `whead_den`, and Denver's own Mode F and physical gust law.
- **Exact Quantitative Gains (`scripts/tool_audit.py`, 120 held-out 2024–25 hours/set, skill vs. 1991–2020 clim):**
  - **Night Coverage Unlocked:** NM/TX day **+0.033**, night **+0.025**; Denver day **+0.005**, night **+0.008**; 90% coverage **0.85–0.93** across all four regimes.
  - **12Z Morning Balloons (~05 h solar):** NM/TX balloon skill jumped from **-0.021** (day model extrapolating) to **+0.016**, while 00Z stayed unchanged (**+0.0099 → +0.0102**).
  - **Denver Replacement:** Replaced the old Denver bundle (**-0.115** skill) with the Denver-trained model (**+0.017**, matching the ERA5 July temperature distribution).
- **Code & Config:** `tempest_weather/assets/`, `assets_denver/`, `assets_denver_allhours/`, `scripts/shipped_check.py`, `scripts/tool_audit.py`.

---

### 1.4 Schaake Shuffle + Whole-Distribution Shear Map (`IL-91` / `F-16`, 2° Blocks `IL-94`/`IL-95`)

- **Concept & Intuition:** After per-column quantile calibration fixes the spread at each individual altitude, the vertical profile can still look slightly jagged or disconnected from height to height — like shuffling the pages of 199 different weather books so each altitude has the right statistics, yet the story from ground to 18 km loses its natural continuity.
  - The **Schaake Shuffle** fixes this by borrowing the exact vertical rank order from real historical atmospheric templates (grouped in 2° geographic blocks), snapping the 199 calibrated members back into physically realistic vertical shapes without altering a single marginal distribution. Pairing it with the **whole-distribution shear map** then gently calibrates the layer-to-layer wind jumps so extreme shear events match real soundings.
- **Technical Implementation:**
  - `tempest/calibrate/shuffle.py` (`--shuffle`, exported via `--post-templates` as `uint8` `199 × 179` rank templates per 2° block; `IL-94`/`IL-95` showed pooled templates kept half the gain while 2° blocks preserved nearly all).
  - `tempest/calibrate/shear_map.py` (`--shear-map`, exported via `--post-smap`) refit *after* the shuffle on 2021–23 calibration years.
- **Exact Quantitative Gains:**
  - **2024–25 Dev (`IL-91`):** Vertical correlation error plunged from **0.056–0.099 → 0.046 / 0.023 / 0.035 / 0.035** (`u / v / T / RH`, beating the 0.05 goal); overall `vcorr_err` **0.076 → 0.039**; shear KS fell from **0.044 → 0.010** (`0.018 / 0.009 / 0.007 / 0.007`, beating the 0.03 goal); `skill15` **+0.0277 → +0.0278**, coverage error **0.0034 → 0.0031**.
  - **Untouched 2026 Jan–Jun Final Test (Descriptive Ablation):** Shear distance **0.0333 → 0.0274**, vertical correlation error **0.0697 → 0.0606**, smaller event-coverage gap, nothing worse.
- **Code & Config:** `tempest/calibrate/shuffle.py`, `tempest/calibrate/shear_map.py`, `tempest/export_tool.py`.

---

### 1.5 Lapse-Rate Map (`L21b`)

- **Concept & Intuition:** Just as wind shear measures how abruptly wind changes with height, the **lapse rate** measures how fast temperature drops as you climb. Raw neural profiles occasionally generate "super-adiabatic" layers — pockets of air that cool faster with height than physics allows for a stable atmosphere, like balancing a bowling ball on top of a beach ball. The lapse-rate map applies the same quantile-mapping idea used for wind shear to vertical temperature steps, restoring physically realistic thermal stratification across every altitude band.
- **Technical Implementation:** `tempest/calibrate/lapse_map.py` (`fit()`, `apply()`), ported to pure NumPy in `tempest_weather/_core.py` with a bit-parity test and exported alongside `l3_c4w` and Denver models (`IL-170 / D-1`).
- **Exact Quantitative Gains (2024–25 Dev):**
  - **Too-Steep (Super-Adiabatic) Layers:** Cut from **33.8% → 23.6%** (closely matching ERA5's **21.9%**).
  - **Temperature Skill:** Improved temperature skill in **every single altitude band**.
- **Code & Config:** `tempest/calibrate/lapse_map.py`, `tempest_weather/_core.py`.

---

### 1.6 Physical 1-Minute ASOS Gust Law + Speed-Switched Regional Law (`P3-1` & `AV13`)

- **Concept & Intuition:** Standard airport METAR reports have a hidden quirk: in light winds, they simply leave the gust field blank ("no gust"), even though the real 5-second wind peak is still ~1.4× the sustained wind. Training a gust model on METAR alone is like estimating waves only when surfers call in a storm warning — it misses everyday turbulence.
  - Refitting the heteroscedastic Gumbel gust law directly on **ASOS 1-minute physical 5-second peaks** fixed this reporting bias. Later, `AV13` added a smart 5 m/s switch: below 5 m/s, use the local station's built-in law; at or above 5 m/s, switch to the regional gust law for stronger cross-station transfer.
- **Technical Implementation:**
  - Heteroscedastic Gumbel regression (`tempest/gust/model.py`): `mu = X @ theta`, `beta = exp(clip(X @ phi, -5, 5))`, `G = max(mu - beta * ln(-ln(u)), 0)`, refit on ASOS 1-minute physical 5-second peaks (NM/TX and Denver DEN+APA).
  - `AV13` speed switch (`tempest_weather/api.py`, `GUST_PHYSICAL = True`, `GUST_SWITCH_WS = 5.0` m/s, `OPTIONS['gust_speed_switch'] = True`).
- **Exact Quantitative Gains:**
  - **Physical 1-Min Refit (2021–23 Val):** CRPS slashed from **1.73 → 0.61 m/s** given a measured wind, and **1.34 → 1.06 m/s** given model winds; storm gusts held accurately at a factor of **~1.35**. (Original METAR Gumbel `P3-1` had already cut CRPS to 1.40 vs. 2.11 for bias-corrected ERA5 `fg10` and 2.21 for a constant 1.48× factor.)
  - **Speed Switch (`AV13` / `b91` on 39,434 Denver DEN+APA test hours):** Cross-station CRPS gain **+1.28% `[+1.11, +1.45]`** over built-in (`+1.09%` in kit `b52`), and **+7.86% `[+6.65, +9.02]`** on windy hours (`>= 5 m/s`, 3,127 h); identical below 5 m/s.
- **Code & Config:** `tempest/gust/model.py`, `tempest_weather/api.py::_gust_params`, `tests/test_gust_speed_switch.py`.

---

### 1.7 Mode F Forecast-Conditioned Network + 50:50 Ridge Blend + Schaake Shuffle (`IL-73`, `IL-77`, `IL-80`, `IL-82`, `v3`)

- **Concept & Intuition:** A climate generator knows what June in New Mexico *usually* looks like, so its skill over climatology is inherently modest (~+0.02–0.03).
  - But 1 to 7 days before launch, a global weather forecast (ECMWF IFS HRES) already sees the exact cold front or jet streak approaching! **Mode F** uses a compact, heavily regularized residual neural network to predict the *error distribution* around the live forecast, blends it 50:50 with a rock-solid linear ridge model so it stays well-calibrated out to day 7, and applies a forecast-error Schaake shuffle so every vertical profile remains physically coherent.
- **Technical Implementation:**
  - Regularized residual network (`IL-77 r1`: width 128, depth 2, `weight_decay = 1e-2`, `lr = 3e-4`, every 4th height input) trained on WeatherBench2 IFS HRES (2016–2020), calibrated on 2021, tested on 2022.
  - Mixed 50:50 with per-lead ridge regression + error pool (`IL-80`), followed by Mode F Schaake shuffle (`IL-82`).
  - Retrained as **Mode F v3** on 00Z + 12Z refetches, widening the served window from `14–20 h` to **`02–20 h` local solar time** (`0.75–7.5` days lead), and built Denver's first Mode F.
- **Exact Quantitative Gains (Test Year 2022, CRPS Skill vs. Climatology at 1 / 3 / 5 / 7 Days):**
  - Raw deterministic HRES: **`0.57 / 0.34 / 0.08 / -0.21`**
  - Regularized Mode F Network (`r1`): **`0.690 / 0.537 / 0.347 / 0.196`**
  - **Shipped 50:50 Network + Ridge Blend (`IL-80`):** **`0.691 / 0.539 / 0.350 / 0.209`**
  - **Mode F Schaake Shuffle (`IL-82`):** Vertical correlation error collapsed from **0.30–0.51 → 0.04–0.12** (CRPS unchanged by construction).
  - **Mode F v3 & Denver:** Retrained v3 adds **+0.04 to +0.06** skill at 05 h solar; Denver Mode F achieves **`0.68 / 0.57 / 0.43 / 0.26`** at 1 / 3 / 5 / 7 days.
- **Code & Config:** `tempest/forecast/modeF.py`, `tempest_weather/forecast.py`, `scripts/il6_modeF.py`.

---

### 1.8 Mode P Past-Date Surface Spread (`F-12`) + 12–18 km RH Hybrid (`F-11a`) + ERA5 Ground-Wind Anchor (`GW-F` / `GW-H`)

- **Concept & Intuition:** When reconstructing a *past* launch date from historical ERA5 reanalysis, three subtle flaws appeared: (1) surface temperature, pressure, and humidity had zero uncertainty spread (pretending ERA5 was exact at the pad), (2) at 12–18 km altitude, a 2022 radiosonde humidity sensor change made the neural residual network worse than simple linear station correction, and (3) the near-ground wind wandered away from ERA5's actual 10 m wind.
  - Fixing all three gave Mode P honest surface uncertainty, accurate stratospheric humidity, and tighter ground wind at both airports and remote basins.
- **Technical Implementation:**
  - `F-12` (`--modep-sfc`): Learned surface residual spread for `t2m`, `sp`, and `rh2m` in Mode P.
  - `F-11 part 1` (`--modep-sta`): Exported `modeP.hybrid_use_network.npy` + `station_map_mix.npz` so `api._past_phys` serves the linear station correction for the 13 RH columns in 12–18 km instead of the neural network.
  - `GW-F / GW-H` (`Launch(past_era5_anchor=True)`, default ON): Centers near-ground past-mode wind on ERA5 10 m wind.
- **Exact Quantitative Gains:**
  - **`F-12` Surface Spread:** CRPS dropped `t2m` **1.16 → 0.68 K**, `sp` **48.8 → 25.9 Pa**, `rh2m` **3.75 → 2.92%**, with `cov99` at **0.99–1.00**.
  - **`F-11a` 12–18 km RH Hybrid:** Test-year CRPS improved from **4.76 → 3.70** (mean 12–18 km RH restored from 4.9% to 10.9%).
  - **`GW-F / GW-H` ERA5 Anchor:** Speed CRPS reduced by **-3% to -11%** (up to **-20%** across 4 sites: TCS, MAF, USCRN Las Cruces basin `0.764 → 0.744`, and USCRN Monahans).
- **Code & Config:** `tempest/forecast/modeP.py`, `tempest/export_tool.py`, `tempest_weather/api.py::_past_phys`, `tempest_weather_v2/launch.py`.

---

### 1.9 Calibrated Vertical-Wind `w`-Head (`P3-2`, `F-27`)

- **Concept & Intuition:** Rather than forcing the main 179-output generator to also predict 44 levels of vertical air motion (`w`, updrafts/downdrafts), Tempest-ARKNET attaches a lightweight conditional sidecar network — the **`w`-head** — that reads a completed horizontal wind + temperature profile and generates matching vertical winds.
  - However, because the `w`-head was trained on *real* profiles but evaluated on *generated* profiles at runtime, its 99% range came out slightly too narrow (`0.984`). Adding a dedicated range calibration map fitted on *generated* inputs (`F-27`) brought its coverage right onto the 0.990 target.
- **Technical Implementation:** Conditional Engression `w`-head (`tempest/output/whead.py`, all-hours `whead_a24` for NM/TX, `whead_den` for Denver) + `spread` quantile table fitted on 2021–23 generated, range-calibrated profiles (`scripts/whead_calib.py`, exported via `--wcalib`).
- **Exact Quantitative Gains (2024–25 Dev):**
  - **Baseline Skill (`P3-2`):** Skill vs. 15-year climatology **+0.0094** (1–5 km), **+0.0141** (5–12 km), **+0.0108** (12–18 km), `-0.0031` (0–1 km).
  - **Calibration (`F-27`):** `cov99` lifted from **`0.984 / 0.985 / 0.984 / 0.982` → `0.989 / 0.990 / 0.990 / 0.991`** (`0–1 / 1–5 / 5–12 / 12–18 km`); spread/skill improved from **0.88–0.93 → 0.97–1.06**; CRPS equal or slightly better (`0.7792 → 0.7781`, `2.4992 → 2.4968`, `2.1437 → 2.1412`, `1.2162 → 1.2170` cm/s).
- **Code & Config:** `tempest/output/whead.py`, `scripts/whead_calib.py`, `tempest_weather/api.py::atmosphere_set`.

---

### 1.10 Station-Scale 10 m Wind & 2 m Temperature Widening (`IL-101` & `L2-H3`)

- **Concept & Intuition:** A `0.25°` weather model grid cell averages wind over a 25 km × 25 km patch of desert, which naturally smooths out local gusts and terrain eddies.
  - Comparing that smooth grid average to a single anemometer on a pole is like comparing the average height of a crowd to one person — the individual point always varies more. `IL-101` widens the forecast-mode wind spread near the ground to match real station-level variance, then smoothly fades the widening back to `1.0` above 150 m so upper-air winds stay untouched.
- **Technical Implementation:** `tempest_weather/bias.py::widen_wind()` scales `u, v` deviations by `k(z) = 1 + (k0 - 1) * exp(-z / 150 m)` using past-only observed forecast-error SDs (`k0 ≈ 1.4–2.2`), preserving member ranks; `widen_temperature()` (`L2-H3`) applies the same principle to 2 m temperature at 7-day leads (enabled when `bias_dir` is present).
- **Exact Quantitative Gains (2025–26 ASOS vs. ECMWF Previous Runs, 17 h solar):**
  - **10 m Station Wind (`IL-101`):** 90% interval coverage jumped from **59–80%** (tool grid SD 1.1–1.6 m/s) to **88–89%** (observed station SD 1.9–2.9 m/s).
  - **2 m Temperature (`L2-H3`):** Leads 1–5 days already 0.90–0.94 (untouched); lead 7 days lifted from **0.79–0.86 → 0.89**.
- **Code & Config:** `tempest_weather/bias.py` (`widen_wind`, `widen_temperature`), `tempest_weather/api.py`.

---

### 1.11 Online EWMA Bias Tracker (`IL-98B`)

- **Concept & Intuition:** Live numerical weather models (ECMWF, GFS) frequently exhibit persistent local quirks at a given airport or launch site — for instance, reading 1 m/s calmer than a desert runway every afternoon. Rather than retraining a neural network to chase these live feed offsets, an **online EWMA (Exponentially Weighted Moving Average) bias tracker** keeps a lightweight rolling scoreboard of recent forecast-minus-ASOS errors and subtracts the verified bias at query time whenever a tracked site is within 60 km.
- **Technical Implementation:** `tempest_weather/bias.py` + `scripts/update_bias.py` (state in `data/ops/bias`, opt-in via `bias_dir` / `TEMPEST_BIAS_DIR`, emits quality flag `surface-bias-corrected`).
- **Exact Quantitative Gains (`scripts/bias_backtest.py`, 2024–2026 Previous Runs leads 1–7 d vs. ASOS, both sites & models):**
  - **Lower MAE in virtually every cell, never worse:** ECMWF temperature **-0.04 to -0.13 K**, GFS temperature **-0.05 to -0.41 K**, ECMWF wind **-0.04 to -0.10 m/s**, GFS wind up to **-0.30 m/s** (only GFS wind leads 2–7 at Spaceport was neutral).
- **Code & Config:** `tempest_weather/bias.py`, `scripts/update_bias.py`.

---

### 1.12 NEXRAD VAD Radar Conditioning (`IL-198` & `O2` Distant Radar)

- **Concept & Intuition:** Surface anemometers only measure wind at 10 meters, leaving a huge blind spot through the 500–2,000 m boundary layer where rockets accelerate and drift.
  - Fortunately, NWS NEXRAD Doppler weather radars continuously emit **VAD (Velocity Azimuth Display)** wind profiles every few minutes! Conditioning Tempest's ensemble on a live radar scan acts like pinning the middle rungs of a ladder — because winds aloft are vertically correlated, knowing 0.5–2 km wind tightens the entire column all the way up to 18 km, even when the radar is 145 km away (`O2`).
- **Technical Implementation:** `tempest_weather_v2/radar.py::latest_profile()` + `Launch.observe_radar()` using `VAD_SIGMA_MS = 3.0 m/s` (confirmed optimal by `C4` sigma sweep `3.0 / 3.02 / 4.16`; `S3` thinning killed for under-coverage).
- **Exact Quantitative Gains:**
  - **El Paso Radar (`IL-198`, 120 days 2021–23 vs. 00Z Balloon, 95% bootstrap):** CRPS gain **+31.3% `[+25.0, +37.5]`** at 2.5–5 km, **+15.2% `[+9.4, +20.9]`** at 5–12 km, **+6.4% `[+2.7, +10.0]`** at 12–18 km (every resample > 0).
  - **Distant Radar (`O2`, Holloman KHDX ~145 km away, 107 common days):** Retains nearly the full El Paso gain with **zero distance decay term**: **+27.6% vs. +29.1%** at 2.5–5 km, **+15.0% vs. +13.5%** at 5–12 km, coverage **0.92 / 0.94**.
  - **Caveat:** Night radar conditioning helps slightly less aloft (**+20%** at 2.5–5 km vs. **+32%** by day).
- **Code & Config:** `tempest_weather_v2/radar.py`, `tempest_weather_v2/launch.py::observe_radar`.

---

### 1.13 Total-Uncertainty Monte Carlo & Hybrid Standard-Air Finding (`montecarlo.py` & `readers.py`)

- **Concept & Intuition:** Flying real Spaceport America Cup rockets through Tempest-ARKNET uncovered a vital engineering truth: if you run a Monte Carlo using *only* weather uncertainty, your predicted apogee scatter is artificially tiny (2–7% wide) and misses the actual flight altitude every time, because rocket drag, mass, and motor impulse errors are **2–4× larger** than weather errors.
  - The solution was twofold: (1) build a **joint Vehicle + Atmosphere Monte Carlo harness** (`montecarlo.py`) that combines `VehiclePriors` with Sobol/LHS atmospheres and attributes variance via Sobol indices, and (2) add a **hybrid `air="standard"` mode** (`readers.py`) so teams whose simulator is already calibrated to ISA density can still inject Tempest's realistic wind profiles, Dryden turbulence, and 1-cos gusts cleanly.
- **Technical Implementation:**
  - `tempest_weather_v2/readers.py::Atmosphere(samples, k, air="standard")` (10 m `float32` fast lookup ~0.7 µs scalar, optional `perturbation=` for Dryden turbulence + 1-cos gust).
  - `tempest_weather_v2/montecarlo.py` (`VehiclePriors`, `run`, `run_importance`, `sobol_indices`, `calibrate_vehicle_sigma`, `AdaptiveConformal`).
- **Exact Quantitative Gains (`FlightSIM&Validation` Sections 12–13, 3 Spaceport America Flights):**
  - **Air Density Accuracy:** Tempest density matches 149 real balloons within **0.5%** (0–10 km, 2024–25), whereas the 1976 Standard Atmosphere is **6.4% off** at the pad.
  - **Hybrid `H0` (`air="standard"` + Tempest Wind):** Lowest 3-flight MAE of all tested variants at **4.89%** (vs. **6.15%** plain standard air, **5.80%** full Tempest past, **5.21%** branch as filed); signed bias cut to **+1.01%** (from `+3.57%`).
  - **Apogee Sensitivity:** Real wind lowered Spaceport Cup apogees by **204–244 ft (1.6–2.0%)** in the right physical direction; turbulence + gusts widened apogee SD by **15–35%** (`94 → 125 ft` on Juno III) with `< 10 ft` median shift.
- **Code & Config:** `tempest_weather_v2/readers.py`, `tempest_weather_v2/montecarlo.py`, `examples/monte_carlo_quickstart.py`.

---

## Tier 2: Partial Wins, Conditional & Opt-In Candidates

These experiments passed their core scientific checks or produced strong regime-specific gains, but remain opt-in, input-gated, or awaiting final approval / global-stage integration (`ASK_LATER`).

---

### 2.1 IFS-Ensemble 24-Feature Mode F (`IL-14` / `ENSF2`, ASK_LATER 21)

- **Concept & Intuition:** A deterministic forecast gives you one best-guess trajectory, whereas a 50-member ensemble tells you both the consensus mean and how much the weather models disagree today. Feeding 24 summary features (ensemble mean and spread at the surface and 500/700/850 hPa) into a dedicated Mode F network lets Tempest tighten its spread on predictable days and widen it when the atmosphere is chaotic.
- **Technical Details & Metrics:** Tested on 2022 across 2–3 training seeds (`data/il14_*.log`, `export --modef-ens`, `api ens_features=`). Lowers 1–7 day forecast CRPS by **-1.9% to -3.1%** in NM/TX and **-1.2% to -2.2%** (`-0.7% to -2.2%` across 3 seeds) in Denver, with `cov99` not worse. Ablation shows **75–90%** of the gain comes from the ensemble mean and the rest from spread. Kept as a separate input-driven network (never merged into one masked trunk, which failed in `N4`).
- **Status:** Passed; input-driven opt-in (`ASK_LATER 21`).

---

### 2.2 SIGMA Lead-as-Noise Scaling (`SIGMA stage 2`, `UR15`, ASK_LATER 43)

- **Concept & Intuition:** At day 1, a weather forecast is sharp and trustworthy; by day 9, it has mostly dissolved back into seasonal climatology. Instead of training four separate choppy lead-time bins (`1 / 3 / 5 / 7 d`) and abruptly falling back to climate after day 7.5, **SIGMA** treats forecast lead time like a smooth volume knob — blending `mu_clim + beta(lead) * (hres - mu_clim) + s(lead) * F` continuously from day 1 through day 10.
- **Technical Details & Metrics:** `tempest/forecast/sigma.py`, `il6_modeF.py --sigma`.
  - **2022 (`b18_sigma_stage2.py`, PASS):** vs. binned Mode F, `-0.3% to -1.7%` at 1–7 d and **-3.9% to -4.8%** beyond 7.5 d; beats climate by **0.55–0.70 CRPS** at days 8, 9, and 10 in all 4 runs.
  - **2023–24 Third Period (`UR15`, `b37`, PASS):** Holds its rule (`-0.0% to -3.3%` at 1–7 d; **-6.9% to -8.2%** at 9 d, interval < 0).
  - **No-PIT Discovery (2026-11-14):** Scoring without the double-fit PIT step lifts SIGMA `cov99` from `0.976–0.983` to **0.987–0.993** at every lead with CRPS within `0.05%`.
- **Status:** Clean PASS across 2022 and 2023–24 (`ASK_LATER 43`); awaiting tool range extension beyond 7.5 days.

---

### 2.3 X4-R Post-Hoc Residual-Referenced Climatology Offset (`X4ERS25`)

- **Concept & Intuition:** When a model trained in New Mexico is asked to predict Denver zero-shot, it brings New Mexico's seasonal averages with it — causing large mean biases (`-0.205` skill).
  - Earlier attempts to retrain the network in anomaly space (`AV21`, `AV40`, `X4a/b/c`) fixed Denver but perturbed NM/TX moisture shapes. **X4-R** solves this *without retraining a single weight*: it measures the exact seasonal harmonic difference between real observations and the frozen network's mean, then applies a soft threshold (`k = 3`) so the offset is **effectively zero inside NM/TX** (preserving 100% of in-domain calibration) while eliminating **~74%** of the transfer bias in Denver.
- **Technical Details & Metrics:** `configs/s25/x4er.toml`, `scripts/x4r_build.py`, ported to `tempest_weather/engine.py::Net.x4r_offset` with a `1.0°` distance cutoff (`tests/test_x4r_port.py`, matches PyTorch to `1.6e-5`).
  - **`X4ERS25` (k = 3, PASS):** Denver `skill15` **+0.1423 / +0.1464** over base (noise `0.0093`, >15× noise); NM/TX `skill15` **-0.0000** both seeds; shape PASS, `preclip` `+0.00006 / +0.00004`, `cov99` OK. Re-check with `AV35` (`b88`) also PASS.
- **Status:** Chosen for final frozen model candidate (Section 28.11), ready for global transfer.

---

### 2.4 Seasonal Width Factors on RH & Surface (`IL-11`)

- **Concept & Intuition:** Humidity and surface air behave differently in dry winter mornings versus monsoon summer afternoons — a single year-round spread factor slightly over-covers in some months and under-covers in others. Applying month-by-month width multipliers *strictly* to humidity and surface variables (after `IL-2` showed applying them everywhere hurt summer temperature aloft) trims overshoot cleanly on both ERA5 and balloons.
- **Technical Details & Metrics:** `score --seasonal models/generator_80_p2f.seasonal2021_rhsfc.npz`, `tempest/calibrate/seasonal.py`.
  - **2024–25 ERA5:** `skill15` `+0.0277 → +0.0279`, `|cov99 - 0.99|` **0.0034 → 0.0025**, no band worse, lowest `cov99` `0.9832`.
  - **2024–25 Balloons:** `skill15` `+0.0083 → +0.0085`, `|cov99 - 0.99|` **0.0039 → 0.0036**, lowest `cov99` `0.9852`.
- **Status:** Kept as an opt-in flag (`--post-seasonal`).

---

### 2.5 UR5 / WD1 10 m Calm/Windy Sequence Chain (`ur5.py`)

- **Concept & Intuition:** Launch windows don't happen in isolated snapshots — if the wind is calm at 08:00, it is far more likely to stay calm at 09:00 and 10:00 than an independent draw suggests (real 3-hour `< 5 m/s` probability is `0.637` vs. `0.409` independent).
  - Moreover, the climate generator's 10 m wind ran ~0.67 m/s windier than ERA5. **UR5 / WD1** maps the 10 m wind speed back to ERA5 quantiles, links consecutive hours with a two-regime (calm vs. windy) Markov chain, and tapers the 10 m adjustment smoothly to zero by 300 m so it never creates an artificial low-level shear cliff.
- **Technical Details & Metrics:** `tempest_weather/ur5.py` (`anchor=True`), `scripts/build_ur5.py`, `OPTIONS['ur5_sequence']`.
  - **`b89` Tool-Path Replay (both seeds):** 3-hour calm-window error slashed from **0.237 / 0.191 / 0.154 → 0.030 / 0.024 / 0.016** (`5 / 8 / 10 m/s`); `cov90` `u 0.887–0.889`, `v 0.888–0.901` (vs. shipped over-covering `0.93 / 0.97`); CRPS `u 1.8206 → 1.8027`, `v 1.5311 → 1.4845`. Anchored chain + 300 m taper fixed the `10→50 m` shear spike (`115.0 / 413.5` back to **`19.0 / 66.5`** vs. off `18.9 / 67.0`).
  - **Caveat:** Formally a technicality MISS on per-hour gap at `5 / 8 m/s` (`0.048 / 0.052` vs. `0.030` limit), passes at `10 m/s`; adopted into final candidate (Section 28.11 item 9) for climate sequences only.

---

### 2.6 Launch-Week Pad Calibration (`IL-207b` / `UR9` / `O3` `Launch.launch_week()`)

- **Concept & Intuition:** A 25 km grid cell cannot know if your specific launch pad sits in a wind-sheltered arroyo or on an exposed mesa. `IL-207` discovered that Truth or Consequences (`TCS`) was under-covered (`0.80`) not because its spread was too narrow, but because of a steady **+1.44 m/s local site bias**. Even a short 7-day record from a pad anemometer (`Launch.launch_week()`) or a per-site factor (`IL-207b`) removes most of this site-specific offset, whereas 1 month of pad data (`M6`) cuts MAE by **-25%**.
- **Technical Details & Metrics:**
  - **`IL-207b` / `UR9` (PASS, 21-day blocks):** `TCS` CRPS **-0.079 / -0.075 / -0.102** (`1.607 → 1.506`, coverage `0.78 → 0.83` / `0.81 → 0.86`); `MAF` neutral to slightly better (`-0.038`).
  - **`O3` / `b90` (`Launch.launch_week(readings)`, k = 7 days, alpha = 1/30):** `TCS` minus auto **-0.0201 `[-0.0411, +0.0009]`** (kit `b38`: `-0.0227`), coverage equal; accepted as a technicality (consistent negative point estimates, small sample of launch weeks). Active automatically whenever pad readings are passed.
- **Code & Config:** `tempest_weather_v2/launch.py::launch_week`, `tempest_weather_v2/sitecal.py`, `tests/test_launch_week.py`.

---

### 2.7 100–300 m Shear Sharpness Finding (`IL-200` / `IL-201`)

- **Concept & Intuition:** Comparing the all-hours tool against 320 pre-2023 balloons revealed that the tool's median wind shear in the 100–300 m layer was noticeably sharper than real balloons — raising the question of whether it was distorting rocket apogee predictions. Running a direct rocket-flight ablation (`IL-201`) proved that stripping *all* interior 100–300 m wind structure changed apogee by less than 1% of its spread — meaning it is a known structural diagnostic to watch for loads/rail-exit work, not an apogee blocker.
- **Technical Details & Metrics:**
  - **`IL-200` (320 balloons 2021–22):** Median shear in `100–300 m` layers: tool **17.5 / 15.4 / 11.7** vs. balloons **14.1 / 12.2 / 9.3** m/s per km (ERA5 `6.7 / 6.5 / 5.0`). Caused by the all-hours generator, not the shear map or `c4w`; a fine-band shear map did not repair it.
  - **`IL-201` (200 atmospheres, Sol Invictus at Spaceport America):** Removing all interior 100–300 m structure moves apogee by **0.9%** and landing distance by **2.0%** of their spreads.

---

### 2.8 Additional Verified Opt-In & Input-Driven Candidates

| ID | Concept & Plain-English Idea | Exact Verified Metrics | Status |
|---|---|---|---|
| **AV35** (`b49`) | **Aloft-Only Balloon Shear Map:** Gently boosts upper-air shear tails (5–12 km half gain, 12–18 km full) while leaving `< 5 km` bit-identical so low-level accuracy is untouched. | Shear `p99` ratio vs. balloons: 5–12 km **0.969** (`19.0 → 20.9` vs. `21.6`), 12–18 km **1.021** (`29.1` vs. `28.5`); CRPS `u+v` only `+0.026%`. Re-passed on `X4-R` (`b88`). | PASS (`ASK_LATER 34`; IN final candidate) |
| **RA 1a / UR3** (`b6`, `b27`) | **Real-Air Grid-to-Point Gap (`Launch.real_air()`):** Adds the measured 6-band difference between a 25 km grid average and a point balloon/anemometer (`1.54–1.98 m/s`) instead of fitting ad-hoc site factors. | 197 left-out stations 90% coverage: `0.831–0.899` → **0.902–0.919** in all 6 bands. At 10 m (`UR3`), `1.54 m/s` beats fitted site factors (`AV6`) at both TCS (`1.248` vs. `1.268`) and MAF (`1.179` vs. `1.271`). | PASS (opt-in `Launch.real_air()`) |
| **NOW2** (`b63`) | **Per-Station 1–6 h Nowcast (`Launch.observe_nowcast`):** Uses the last 6 hours at the site plus 3 hours at the 3 nearest ASOS stations to predict short-term wind evolution. | vs. `observe()`: **+8.3 / +8.5 / +8.2 / +7.0%** CRPS at `+1 / 2 / 3 / 6 h` (2015–17 holdout); `cov90` **0.907–0.908**; every one of 9 stations improved. | PASS (`ASK_LATER 37`; input-driven) |
| **DP Tower** (`b67`) | **200 m Pad Tower / Drone Profiler (`Launch.observe_tower`):** Assimilates low-level tower winds (`<= 200 m`, `sigma = 0.5 m/s`) directly into the launch-day pool. | SWiFT 200 m tower (130 h): 50–150 m wind CRPS cut by **50.1% `[12.8, 72.1]`** at 30 min (`1.575 → 0.805`) and **37.2%** at 60 min. | PASS (`ASK_LATER 39`; site-specific) |
| **N2 / AV29** (`b19`) | **Global World-Start Pre-Training + 500 Box Steps:** Pre-train Mode F on 63.6M global HRES–ERA5 pairs, then fine-tune 500 steps on the local region — worth ~3 years of local forecast data (`N2-B`). | Pooled 2021+2022 (3 seeds): **-0.7% to -2.5%** vs. own+500 (wins 4/4/4 NM/TX, 3/3/4 Denver). Data-scarce 1-yr box (`N2-B`): **-1.9% to -5.1%** (16/16 intervals < 0). | PASS (queued for global stage) |

---

## Tier 3: Neutral, Tied, or Inside Seed Noise (No Net Gain)

These experiments did not actively break the system, but their effects sat inside seed-to-seed noise, tied the baseline, or traded one metric for another with no clear net win.

---

### 3.1 2026 Jan–Jun Final Test vs. E12 Per-Variable CRPS Tie

- **Concept & Intuition:** After months of upgrading the generator, calibration, and shape stack, the untouched 2026 Jan–Jun final test asked whether the new model beat the earlier `E12` baseline on *individual single-variable* CRPS. The honest answer: on per-variable CRPS alone, both models are statistical ties in all 38 cells — proving that the real value of the newer system lies in **vertical coherence, shear distribution, surface spread, forecast blending, and launch-day tools**, not raw single-level climatological predictability (which is physically capped near `+0.02`).
- **Exact Metrics (`docs/results/FINAL_REPORT.md`):** ERA5 `skill15` **+0.0209** vs. E12 `+0.0204`; Balloons **+0.0187** vs. E12 `+0.0160`; `|cov99 - 0.99|` **0.0049 / 0.0064** vs. E12 `0.0047 / 0.0063`. All 38 variable × band cells are statistical ties. Both models have negative skill on `T 12–18 km` (`-0.030` ERA5, `-0.039` balloons) due to the ~2020 tropopause regime shift (`IL-67`).

---

### 3.2 8-Seed Ensembles (`IL-3`)

- **Concept & Intuition:** If averaging 4 independently trained neural networks reduces variance, doubling the ensemble to 8 networks might squeeze out extra accuracy — like asking 8 forecasters instead of 4. In practice, 4 members already saturate the variance reduction, so doubling to 8 only doubled inference cost and bundle size for noise-level movement.
- **Exact Metrics (`configs/generator_il3.toml`):** ERA5 `skill15` `+0.0277 → +0.0278` (noise), `cov99` error `0.0034 → 0.0031`; Balloons `+0.0083 → +0.0071` (wrong direction, inside noise). Discarded; 4 members kept.

---

### 3.3 `observe()` vs. Plain Persistence at TCS/MAF (`a1_bootstrap`)

- **Concept & Intuition:** One hour after an airport reports its 10 m wind speed, simply predicting "next hour's wind will look like this hour's wind plus historical regression" (plain persistence) is a surprisingly tough benchmark. Testing Tempest's `observe()` head-to-head on identical hours showed it ties persistence at Truth or Consequences and trails slightly at Midland — proving that single-station surface persistence is already near the predictability ceiling at 1-hour lead (while `observe()`'s real advantage is propagating the observation coherently up through the full 18 km column).
- **Exact Metrics (`a1_bootstrap.log`, 300 matched hours, date-block bootstrap):** `TCS` **-0.011 m/s `[-0.046, +0.026]`** (no difference); `MAF` **+0.037 m/s `[+0.007, +0.067]`** (tool 3.9% worse; earlier "7–10% worse" figure was from unmatched hours).

---

### 3.4 Order-Statistic vs. Quantile Mismatch Check (`F-23`)

- **Concept & Intuition:** Technically, the minimum and maximum of 199 random draws sit at expected quantile positions `1/200` and `199/200` (`0.005` and `0.995`), which can differ slightly from pooled empirical quantiles. Checking whether re-scaling the outer knots to match exact order-statistic coverage mattered revealed a tiny `+0.002` constant over-coverage — well inside sampling and seed noise, so no extra complexity was warranted.
- **Exact Metrics (`scripts/f23_check.py`, 2,500 rows):** Mean min–max coverage of 199 draws = **0.9920** (fit years) and **0.9919** (2024–25); removing it would move mean error by `< 0.0005` (inside seed spread). No change.

---

### 3.5 Full PIT Recalibration Alone (`IL-86`)

- **Concept & Intuition:** Probability Integral Transform (PIT) recalibration warps every predicted CDF so that historical truth falls uniformly across all percentiles — like ironing out wrinkles in a bedsheet. While it did iron out per-level coverage and cut tail-rate error by 26%, it slightly *worsened* overall PIT distance out-of-sample and nudged shear KS upward, yielding a mixed verdict.
- **Exact Metrics (`scripts/il86_fit.py`, `--pit-recal`):** Per-level coverage error `0.0123 → 0.0101` (better), tail-rate error `2.90 → 2.13` (-26%), skew `0.112 → 0.089`, kurtosis `0.34 → 0.31`; **but** PIT distance `0.0372 → 0.0387` (worse than 0.0010 tolerance) and shear KS `0.0090 → 0.0135`; ERA5 `skill15` `+0.0277 → +0.0271`. Flag kept OFF.

---

### 3.6 Chronos-2 vs. Ridge Regression for Climate Indices (`IL-7a`)

- **Concept & Intuition:** For forecasting multi-month climate drivers (ENSO `ONI`, `WWV`, `QBO30`, `QBO50`), a 120-million-parameter foundation time-series transformer (`Chronos-2`) sounds much fancier than a 6-lag linear ridge regression. Yet on 2012–2025 hindcasts, the giant transformer tied simple ridge regression on `ONI` and `WWV` and **lost** on `QBO` — proving that a tiny, zero-dependency NumPy ridge model is both faster and more accurate.
- **Exact Metrics (`scripts/chronos_bakeoff.py`, 1–12 mo mean CRPS):** `ONI` ridge **0.342** vs. Chronos-2 `0.337` (alone) / `0.348` (covariates); `QBO30` ridge **4.63** vs. Chronos `5.16`; `QBO50` ridge **2.75** vs. Chronos `2.99–3.06`; `WWV` ridge `4.48e13` vs. Chronos `4.36e13` (cov) / `5.79e13` (alone). Ridge kept.

---

### 3.7 Shear-Tail Stretch (`W1`/`W5`/`W6`) & Balloon-Correlation Gaussian Copula (`V5a` / `X1`)

- **Concept & Intuition:** To push upper-air vertical correlation and shear tails even closer to balloons, two post-processing families were tested: (1) stretching the rough high-frequency wind component per band (`W1`/`W5`/`W6`), and (2) replacing ERA5 Schaake templates with a Gaussian copula fitted to real balloon correlations (`V5a`, `X1`).
  - Both families hit a classic whack-a-mole ceiling: stretching fixed 3 of 4 bands but spilled across band edges into 1–5 km (`1.12–1.20`) and added `+0.005` correlation error; the copula lowered correlation error on seed 0 (`0.044`) but failed on seed 1 (`0.058`, `T` CRPS `+0.35%` / `u` `+0.9%`), and locking marginals (`X1`) still over-produced low-Richardson-number (`Ri < 1`) turbulence layers (`0.318` vs. balloons `0.196`).
- **Exact Metrics:** `W1/W5/W6` (`b81`, `b83`): `p99` `1–5 km` overshoots to `1.12–1.20`, `vcorr_err` `+0.0045 to +0.0052` (limit `+0.003`). `V5a` (`b71`): seed 0 err `0.044` (`T` CRPS `+0.35%`), seed 1 err `0.058` (`u` CRPS `+0.9%`). `X1` (`b86`): corr gain only `-0.0011 / -0.0039` (needs `-0.005`), `Ri < 1` `5–12 / 12–18 km` `0.318 / 0.202` vs. balloons `0.196 / 0.154`. Line closed.

---

### 3.8 HRRR vs. ERA5 at Remote USCRN Basin Station (`GW-C` / `GW-F`)

- **Concept & Intuition:** NOAA's 3 km HRRR model looks dramatically better than 25 km ERA5 when scored at airports — but that is an illusion caused by **truth contamination**, because HRRR directly assimilates airport ASOS reports! When evaluated at an independent, non-assimilated USCRN desert basin station (Las Cruces 20 N, 27,132 hours), HRRR showed **no advantage over ERA5**, and anchoring to HRRR did not help the Spaceport America flight-sim runs (`F`: Prometheus `+9.9%`, Juno III `+4.8%`).
- **Exact Metrics (`docs/HANDOVER_2026-11-09.md`, `FIVE_DAY_PLAN.md`):** ERA5 vs. USCRN hourly speed correlation = **0.85**; past-mode CRPS `0.764` → ERA5 anchor `0.744` vs. raw ERA5 `1.163`; HRRR offers no edge at unassimilated remote pads.

---

### 3.9 Optimizer & Whole-Profile Loss-Mix Sweeps (`S25 GF2` & `S25 GF1`)

- **Concept & Intuition:** To verify whether the shipped Engression training settings (`lr = 1e-3`, `wd = 1e-4`, `es_weight = 0.1`) were leaving accuracy on the table, `GF2` swept a 3×3 optimizer grid and `GF1` swept 11 whole-profile loss terms (variogram score, shear-vector energy score, energy-score exponent `beta`, threshold-weighted ES `GX2`). Every single candidate landed inside training seed noise — confirming the shipped optimizer and loss mix sit right at the flat optimum.
- **Exact Metrics (`kit_s25_gf2.log`, `kit_s25_gf1_screen.log`):**
  - **`GF2` (KILL):** Best cell (`lr 1e-3, wd 1e-5`) val CRPS `-0.00106` vs. seed noise `0.00428`; `lr 3e-3` worse by `0.003–0.004`.
  - **`GF1` (KILL):** Best arm (`vario01`) composite target `0.9934` vs. `1.0000` (gain `0.0066` < seed noise `0.0087`); `d_skill15(b)` within `-0.0003..+0.0005` for all 11 arms.

---

## Tier 4: Unsuccessful, Rejected, or Actually Negative Impact (Post-Mortems)

These experiments degraded accuracy, broke calibration, overfit catastrophically, or failed their physical premise. Keeping their post-mortems documented prevents future contributors from repeating dead ends.

---

### 4.1 Driver Interactions (`F-14` & `IL-97`) — *Catastrophic Overfitting*

- **Concept & Intuition:** Climate indices like El Niño (`ONI`) and stratospheric winds (`QBO`) physically interact in the real atmosphere, so letting the slope network multiply them together seemed logical. The trap is **effective sample size**: across 30 training years, there are only ~35 independent ENSO/QBO states. Giving a neural branch freedom to combine slow-moving indices is like trying to fit a curved 20-parameter polynomial to 35 coin flips — it memorizes the past and collapses on new years.
- **Post-Mortem & Exact Metrics:**
  - **`F-14` (`p2fint`, DISCARDED):** ERA5 `skill15` unknown collapsed from **`+0.0277 → +0.0003`**, known from **`+0.0293 → -0.0272`**, balloons from **`+0.0084 → -0.0178`**, coverage error worsened **`0.0034 → 0.0050`**.
  - **`IL-97` (`p2fpp`, restricted explicit `oni*qbo30`, `oni*qbo50` products, DISCARDED):** ERA5 `skill15` `+0.0277 → +0.0274`, balloons `+0.0084 → +0.0079`, and **4 shape metrics degraded** (coverage error, PIT, pre-clip rate, tail rate). Climate drivers stay strictly additive.

---

### 4.2 Rectified Flow Matching (`S25 GF3`) — *KILL*

- **Concept & Intuition:** Flow matching learns a smooth multi-step velocity field from pure noise to a full atmospheric profile, theoretically capturing the entire joint 44-height density without needing a post-hoc Schaake shuffle. In practice, because flow matching is trained with a velocity MSE loss rather than a proper probabilistic scoring rule (CRPS), it lost skill, failed shape checks in every arm, and cost **8× more compute** at inference.
- **Post-Mortem & Exact Metrics (`kit_s25_gf3.log`):**
  - `F1` (8 Euler steps): `d_skill15(b)` **-0.0018 / -0.0029** (vs. floor `-0.0009`), shape FAIL (`pit_tv`, `shear_ks`, `vcorr_err`), target `1.36 / 1.35` vs. base `1.00 / 0.98`.
  - `F2` (`F1` + 1000 steps CRPS fine-tune): `d_skill15(b)` **-0.0072 / -0.0107**, shape FAIL + `cov99` FAIL.
  - Sampling cost: **7.9×** the one-step Engression MLP. Denver report: `-0.09 / -0.10`.

---

### 4.3 Prior-Sample Input + Learned Residual (`S25 H1`) — *KILL*

- **Concept & Intuition:** Instead of generating an atmosphere from pure random noise, `H1` fed the network a synthetic Earth-GRAM-style AR(1) prior sample and asked it to learn only the residual correction — like giving an artist a rough sketch to refine. Surprisingly, the network performed **worse than an identical control fed pure `N(0,1)` noise**, because the rigid Gaussian prior conflicted with real non-Gaussian weather structures.
- **Post-Mortem & Exact Metrics (`kit_s25_h1.log`):** Prior minus `N(0,1)` control `skill15` **-0.0052 / -0.0053** (noise `0.0012`); `d_skill15(b)` vs. base **-0.0033 / -0.0040** (FAIL); shape FAIL (`event_cov_gap`, `kurt_diff`); Denver `-0.20 / -0.19`. Gated follow-up `H4` was cancelled.

---

### 4.4 Split Validation Windows (`F-7` & `F-7b`) — *Worse Than `p2f`*

- **Concept & Intuition:** Because `p2f` used 2021–23 for both early stopping and calibration, `F-7` carved out 2019–20 as a separate validation set (`train <= 2018`) and `F-7b` held out random 14-day blocks from `<= 2020`. Removing two recent warming years from training hurt skill by `0.002–0.003` while yielding **zero coverage improvement** — proving that the early-stopping overlap was harmless (`p2f` doesn't even early-stop before step 6000) and recent training years are valuable.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L51):**
  - **`F-7` (`p2fv`):** ERA5 `skill15` **`+0.0277 → +0.0243`** (`-0.0034`), balloons `+0.0084 → +0.0070`.
  - **`F-7b` (`p2fb`):** ERA5 `skill15` **`+0.0277 → +0.0254`** (`-0.0023`), balloons `+0.0084 → +0.0069`.

---

### 4.5 Height-Token Transformer Generator (`IL-8` & `S25 GT2`) — *Too Slow & Hurts Skill*

- **Concept & Intuition:** Inspired by `Chronos-2`, `IL-8` treated the 44 altitudes as sequence tokens with self-attention along height instead of a flat MLP. The first run (`IL-8`) was aborted at step 500 for extreme cost (1,700 s per 500 steps, worse validation `1.29` vs. `1.08`). When the cheaper `IL-8b` (`d=96`) was finally finished and pooled with MLP members in `S25 GT2`, the token members severely dragged the ensemble down.
- **Post-Mortem & Exact Metrics (`kit_s25_gt2.log`):** `d_skill15(b)` **-0.0321 (seed 0) and -0.0286 (seed 100)** (far below `-0.0009` floor); shape FAIL in both seeds (`event_cov_gap`, `shear_ks`, `skew_diff`, `vcorr_err`, `pit_tv`, `tail_rate_err`); Denver `-0.18 / -0.19`.

---

### 4.6 `W2` u,v Gaussian Copula (`b79`, `26.2`) — *CRPS Cost & Low-Ri Overshoot*

- **Concept & Intuition:** Applying a balloon-fitted Gaussian copula to `u, v` wind columns alone avoided the temperature CRPS penalty of `V5`, and lowered vertical-correlation error on seed 0 (`0.035`). However, it repeatedly added a `u` CRPS penalty on seed 1 and over-generated turbulent `Ri < 1` layers aloft — and combining it with a damped shear stretch (`26.2`) made `Ri < 1` even worse (`0.244` vs. balloons `0.154`).
- **Post-Mortem & Exact Metrics (`kit_b79_w2_copula_uv.log`, `kit_b84_combined_copula_stretch.log`):** `W2` seed 0 `Ri < 1` 12–18 km **0.187** (balloons `0.149`), seed 1 `u` CRPS **+0.41% to +0.9%** (exceeding `0.3%` limit). `26.2` combined arm: `Ri < 1` **0.244 / 0.218**, `u` CRPS `+0.43%`, correlation gain vanished.

---

### 4.7 Final `m=8` Samples & RH-in-Loss Training (`F-15`, `F-19`, `L2-H4`)

- **Concept & Intuition:** Increasing training samples per row from `m = 4` to `m = 8` for the final 1,500 steps (`F-15`) aimed to reduce gradient noise, while adding an explicit percentage-RH CRPS term (`F-19`) aimed to weight near-saturation humidity errors more heavily. Neither helped: `m = 8` degraded vertical correlation, `F-19` increased pre-clip RH violations, and combining them (`L2-H4`) ran out of GPU memory at `m=6` and lost skill at `m=5`.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L60, L63, L377):**
  - **`F-15` (`p2fm8`):** ERA5 `skill15` flat (`+0.0277`), balloons `+0.0084 → +0.0083`, `vcorr_err` **worse `0.0764 → 0.0787`** (exceeding `0.0015` tol).
  - **`F-19` (`p2frh`, weight 0.3):** ERA5 `+0.0277 → +0.0276`, pre-clip RH rate **worse `0.0256 → 0.0267`**.
  - **`L2-H4` (`p2fmix`, `m=5`):** ERA5 **`+0.0277 → +0.0274`** (FAIL), balloons **`+0.0084 → +0.0070`**.

---

### 4.8 Trajectory-Aware Balloon First Guess (`F-10`) — *Worse Temperature Aloft*

- **Concept & Intuition:** A real weather balloon takes ~90 minutes to climb to 18 km and drifts 20–80 km downwind. Reading ERA5 along the drifting balloon's trajectory instead of straight up above the launch pad seemed more physically faithful — yet on `0.25°` hourly ERA5, stepping across coarse grid cells introduced interpolation error that made 5–12 km temperature **9.2% worse**.
- **Post-Mortem & Exact Metrics (`scripts/f10_check.py`, 2,548 soundings 2024–25):** MAE change: `T 0–1 km` `+0.7%`, `T 1–5 km` **`+3.5%`**, `T 5–12 km` **`+9.2%` (worse)**, `u/v` `-1.8% to +0.9%`. Launch-point first guess kept.

---

### 4.9 Post-2022 Sensor Indicator in Mode P (`F-11` Part 2)

- **Concept & Intuition:** Radiosonde humidity sensors changed around 2022. Feeding Mode P a binary `post_2022` flag was meant to let the network adjust its mean to the modern sensor while still learning dynamics from 1991–2017. In reality, the hybrid station correction (`F-11` part 1) already handled the shift, and the binary indicator slightly worsened network CRPS.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L56):** Mode P network + range map CRPS **`1.9346 → 1.9416`** (`RH 12–18 km` `+0.082`), hybrid CRPS `1.8673 → 1.8692`. Discarded.

---

### 4.10 Station-Blend Training Dataset (`F-20`)

- **Concept & Intuition:** Because the pilot box only has two radiosonde stations, nearest-station assignment created a theoretical Voronoi seam near `104.4° W` and a solar-hour switch at `11:00`. Stochastically blending stations by inverse distance and cosine hour weights required rebuilding the entire 8M-row dataset, yet failed to improve balloon skill and actually made the `u 1–5 km` seam slightly *more* pronounced.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L64):** Balloons `skill15` `+0.0084 → +0.0077`, ERA5-type `+0.0277 → +0.0266`; seam ratio `u 1–5 km` **worse `1.16 → 1.31`** (`T 1–5 km` `1.05 → 0.78`). Build flag kept OFF (provenance sidecar `F-35` kept).

---

### 4.11 Gust Stability Inputs (`F-26`) & Soak-Library Wind Matching (`F-25`)

- **Concept & Intuition:** Two intuitively appealing upgrades to secondary modules failed their benchmarks: (1) adding 500 m wind and lapse-rate stability to the gust model (`F-26`) added zero predictive skill beyond 10 m wind + season + hour, and (2) matching 24-hour pad soak histories on 10 m wind + RH in addition to `t2m` (`F-25`) forced poorer temperature matches and actually **worsened** wind-history CRPS.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L69–L70):**
  - **`F-26` (DISCARDED):** 2024–25 CRPS `1.4552 → 1.4542`, MAE `2.018 → 2.020`, `cov99` `0.985 → 0.984`.
  - **`F-25` (DISCARDED):** Wind-history CRPS **worse**: `T-6..T-1 h` **`0.960 → 1.044 m/s`**, `T-24..T-1 h` **`0.777 → 0.798 m/s`**.

---

### 4.12 Seasonal Widths Beyond RH/Surface (`IL-2`)

- **Concept & Intuition:** Applying month-by-month spread multipliers across *all* variables was meant to fix the summer `T 5–12 km` coverage dip. Instead, because 2021–23 summers did not show the miss, the factors mostly shrank spreads — making the target `T 5–12 km` cell and the event-coverage gap **worse**.
- **Post-Mortem & Exact Metrics (`PLAN.md` L972, `FINAL_REPORT.md`):** Target cell `T 5–12 km` `cov99` fell **`0.9832 → 0.9805`**; event-coverage gap worsened. Salvaged strictly for RH + surface only (`IL-11`).

---

### 4.13 Median Bias Shifts (`IL-13`, `IL-66`, `IL-72`)

- **Concept & Intuition:** When a model shows a `-0.4 K` cold bias in 2024–25, shifting the median by the 2021–23 residual looks like an instant fix. In reality, atmospheric bias drifts nonlinearly from year to year (and shifts on bounded RH columns push samples out of bounds), so fixed median shifts either did nothing or broke coverage.
- **Post-Mortem & Exact Metrics:**
  - **`IL-13` (2021–23 shift, DISCARDED):** `RH 1–5 km` coverage collapsed **`0.9949 → 0.9758`**; 2021–23 shifts were tiny (`+0.03 K`).
  - **`IL-66` (2011–2023 shift, DISCARDED):** ERA5 `skill15` **`+0.0277 → +0.0266`**, `cov99` error doubled **`0.0034 → 0.0072`**, lowest band **`0.9203`**.
  - **`IL-72` (2022–23 balloon shift, DISCARDED):** `T` offset `0.00 K`, RH `-3.2%`; balloons `skill15` `+0.0084 → +0.0079`.

---

### 4.14 Trust Layer (`P1-d`, `IL-10`, `AV34S25`) & Rare Shear Patches (`IL-5`, `IL-12`)

- **Concept & Intuition:** Two early post-processing ideas failed to generalize cleanly to the final stack: (1) blending weak generator bands back toward 15-year climatology (`Trust Layer`) initially boosted `rh2m` slightly, but broke RH/balloon coverage and failed shape checks (`event_cov_gap`, `shear_ks`) on both seeds when rebuilt on `l3_c4w` (`AV34S25`); (2) injecting Earth-GRAM-style rare severe shear patches (`IL-5`, `IL-12`) traded a better 99.9th percentile for an inflated 99th percentile because the 99.9th target itself shifted 14% between 2021–23 and 2024–25.
- **Post-Mortem & Exact Metrics:**
  - **`P1-d` / `IL-10` / `AV34S25` (KILL):** `P1-d` dropped `RH 5–12 / 12–18 km` `cov99` to `0.9747 / 0.9673` and wind 5–18 km skill `-0.005 to -0.007`; `AV34S25` on `c4w` failed shape (`event_cov_gap`, `shear_ks`) in both seeds with seed 100 gain inside noise.
  - **`IL-5` / `IL-12` (DISCARDED):** `IL-5` pushed 99th shear up 4–8% (`17.92 → 19.3`); `IL-12` (5–12 km only) was indistinguishable from `p2f`.

---

### 4.15 Weibull-Space Wind Head (`W4`) — *Premise Failed*

- **Concept & Intuition:** Wind speeds are famously modeled by Weibull distributions, so predicting 10 m wind in Weibull space seemed like a natural way to fix the shortage of calm hours (`< 1 m/s`). A quick premise check (`scripts/w4_premise_check.py`) revealed that the calm shortage lives in **ERA5 itself** (1.2% calm vs. ASOS 6.1%), and the tool's Weibull shape parameter (`k = 2.05`) was already *lower* than both ERA5 (`2.34`) and ASOS (`2.23`) — proving the model was not "too Gaussian."
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L516):** Dropped before training.

---

### 4.16 Difference Assimilation (`P1`) & Regime-Dependent Spread (`P4`)

- **Concept & Intuition:** Two launch-day ground-wind hypotheses failed their physics checks: (1) assimilating the *difference* between a station's reading and the tool's prediction at the station (`P1`) was meant to cancel siting bias, but because the coarse tool predicts the exact same grid value at both station and pad, difference assimilation reduced algebraically to the raw update (neutral); (2) scaling past-mode wind spread by day/night × boundary-layer depth (`P4`) failed because the needed spread factor is a **property of the site** (airport vs. basin), not the meteorological regime.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L524, `FIVE_DAY_PLAN.md` L103):** `P1` neutral; `P4` FAIL.

---

### 4.17 Gust-as-Aloft-Wind Measurement (`P2`) — *Too Small*

- **Concept & Intuition:** During a deep afternoon mixed layer, surface gusts bring momentum down from 300–750 m aloft, suggesting a surface gust report could serve as a free proxy for low-level wind aloft. In practice, using raw gust reports unconditionally yielded only **-2.3%** MAE gain in mixed air and **~0%** at night — too small to adopt globally (though later BLH-gated `AV36` showed `+5.3% to +7.4%` MAE gain in deep boundary layers `>= 1000 m`, it still lacked an ensemble/BLH runtime input).
- **Post-Mortem & Exact Metrics (`FINAL_REPORT.md` §10, `AUTOPILOT.md` L524):** Unconditional `P2` rejected (`-2%` / `-2.3%` in mixed air, `~0` at night).

---

### 4.18 Terrain-Based Site Calibration (`P7` / `IL-168` / `SV stage 1`)

- **Concept & Intuition:** If every launch pad has its own wind bias, could we predict that bias from static terrain maps (NLCD roughness `z0`, topographic position index, ridge distance, elevation offset) without ever placing an anemometer at the pad? Leave-one-site-out tests across 8 in-box sites (`P7`) and 280 stations (`SV stage 1`) proved that static terrain descriptors explain almost nothing (**~0.5% to 4%** of the site offset) — only real on-site readings work.
- **Post-Mortem & Exact Metrics (`AUTOPILOT.md` L525, `New_Plan.md` L355):** `P7`: terrain adds only **~0.5%** over a single constant regional factor (8 sites). `SV stage 1` (280 stations): `k0` terrain-only gain **0.004 `[-0.036, 0.032]`** (4% of full fit `0.113`).

---

### 4.19 Zero-Shot NM/TX `c4w` in Denver — *Degrades Temperature Transfer*

- **Concept & Intuition:** Adding the near-ground vector-wind loss (`c4w`) boosted wind and RH skill inside New Mexico/Texas, so it was checked zero-shot in Denver. Surprisingly, it made **temperature transfer worse** in Denver across both training seeds — proving that regional models (or post-hoc `X4-R` offsets) are mandatory when crossing into a new climate regime.
- **Post-Mortem & Exact Metrics (`FINAL_REPORT.md` §10, `AUTOPILOT.md` L521):** FAIL on Denver zero-shot temperature transfer on both training seeds; Denver kept its own locally trained models (`l3_blocal_c4w` / `a24den_c4w`).

---

### 4.20 Previously Shipped Small Denver Model (`generator_denver.pt`) — *Below Climatology*

- **Concept & Intuition:** An early audit of the *actually installed* Denver bundle (`scripts/shipped_check.py`) caught a silent failure: the small 2016–21 Denver model that had been shipped previously scored **-0.115 below climatology** on 2024–25 — worse than simply guessing historical monthly averages! Catching this led directly to replacing it with the full Denver-trained `l3_blocal_c4w` / `a24den_c4w` models (`+0.017`) and establishing an export-gate rule (`IL-171`) requiring every exported bundle to be scored end-to-end before installation.
- **Post-Mortem & Exact Metrics (`FINAL_REPORT.md` §11, `AUTOPILOT.md` L527, L538):** Old bundle **-0.115** → replaced with Denver-trained model **+0.017** (every band improved).

---

### 4.21 Additional Notable Kills from `New_Plan.md` (Mode F & Calibration)

| ID | Concept & Plain-English Idea | Exact Failure Metrics & Lesson |
|---|---|---|
| **N4** (`b5_modeF_mask.py`) | **Optional Ensemble Inputs in One Trunk:** Feed one Mode F network both HRES-only (zeros + mask bit) and ensemble-present rows to avoid maintaining two checkpoints. | **KILL:** Worse by **+1.0% to +2.6%** on both sides across boxes/seeds. Never feed two different input worlds into one trunk; keep two single-purpose networks. |
| **N5** (`b5_modeF_alllead.py`) | **One All-Lead Network (Day 1 to Climate):** Train a single plain residual network across leads 1–10 d plus 10% climate anchors. | **KILL:** Worse by **+2.4% to +2.7%** at 1 d and **+0.9% to +1.1%** at 3 d (limit `+1%`). Superseded by `SIGMA`, which handles lead-dependent variance analytically. |
| **Uniform RH Stretch** (`b3_rh_widen.py`) | **Uniformly Stretch 12–18 km RH (`k = 1.95`):** Widen the whole distribution to pull `cov99` from `0.948` up to `0.991`. | **FAIL:** Cost **+5.9% CRPS** (`3.704 → 3.924`, limit `+1.5%`). You cannot fix a 4% tail shortfall by inflating the entire middle of the distribution. |
| **UR1 / X2** (`b25`, `b85`) | **Year-Specific Tail Calibration (`TAILCAL`):** Fit per-lead outer-5% tail stretch factors on 2021 and apply to 2022 (or pooled 2021+2022 → 2023–24). | **KILL:** Factors jumped by **0.26–0.995** between fit years (limit `0.15`), and `X2` still left 1 d `cov99` `0.03–0.13` short out of period. Dropping the double-fit PIT step solved 5–9 d cleanly instead. |
| **AV11** (`b40`) | **Past-Mode Wind Spread ×1.2 at Airports:** Widen past-mode ground wind spread by 20% at airport sites. | **KILL:** Improved MAF (`-0.029`) but worsened LRU (`+0.024`), PEQ (`+0.019`), and ELP (`+0.001`). Airport shortfall is a **location bias**, not a spread defect. |
| **N1C4W / AV19S25** (`s25`) | **Cross-Fit & Student-t Rebuilt on `c4w` Base:** Re-tested earlier `p2f` PASSes (`N1`, `AV19`) directly on the newer `l3_c4w` paired base. | **KILL:** `N1C4W` failed shape in both seeds (`cov_err_mean`, `pit_tv`); `AV19S25` worsened Denver (`-0.0103 / -0.0039`) and failed shape (`kurt_diff`, `preclip_rate`). Proved gains on an older base must always be re-verified on the current stack. |
