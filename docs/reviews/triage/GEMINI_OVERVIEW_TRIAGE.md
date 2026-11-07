# Gemini overview of Tempest-ARKNET: fact-check and resulting dev actions

**User decisions 2026-11-06 → `docs/plans/LAUNCH_PLAN.md`:** A1 = modified (c), no retrain, fused extension to 80 km; A2 = flexible launch-day correction from any readings (not only balloons); A3 = yes; A4 = only the vehicle-free tracer-drift check (the user has their own DOF simulator with Monte Carlo; the tool stays vehicle-agnostic).

Written 2026-11-06. Suggested home: `docs/reviews/triage/GEMINI_OVERVIEW_TRIAGE.md`, with the actions copied into `To-do-Concise.md`.
Checked against the public GitHub copy of `senai-sorsa/tempest-arknet` (shallow clone, 2026-11-06). Local commits that haven't been pushed yet (ASK_LATER 2) were not visible, so a few "missing" items may already be fixed locally.

---

## 0. Bottom line

The Gemini text describes the system, it doesn't review it. It read the file tree and docstrings and wrote a confident walkthrough, but it never looked at results, flags or the final test. It gets the overall structure right (ingest, profiles, generator, calibrate, forecast, tool). It gets **six things materially wrong**, and two of them would mislead anyone planning a real launch with this tool: the altitude ceiling and what "Mode P" means.

There are three practical uses for it:
1. **As a check on how readable the docs are.** If a careful outside reader gets the ceiling, the scope and the modes wrong, then the README and the `tempest_weather/README.md` don't state them prominently enough.
2. **As a list of user requirements.** Strip out the errors and the text is a good statement of what a rocket Monte Carlo user expects: 30+ km, day-of-launch balloon conditioning, downrange coherence, shear tails, and plug-in output for a 6-DOF simulator. Those expectations are the real gap list (section 3).
3. **Not as an architecture or method guide.** It recommends nothing the repo hasn't already tried, and several things it presents as active features were tested and **switched off** (section 4).

---

## 1. Fact-check: claim vs repo

| # | Gemini claim | What the repo actually does | Severity | Action |
|---|---|---|---|---|
| 1 | Profiles "from the ground up to 30+ km" | 44 fixed heights, **10 m to 18 km AGL** (`tempest/profiles/to_heights.py: HEIGHTS`) | **High**: a rocket going past 18 km would get no atmosphere above that height | A1 (decide), D1 (document) |
| 2 | Global system; launch sites Canaveral, Vandenberg, Fairbanks | Production covers the **pilot box only** (31–34 N, 108–101 W: Spaceport America and Midland) and refuses other places. `region_g2_*.toml` are training boxes for the global loop (Loop 3, G2), not served sites | High | D1 |
| 3 | **Mode P = persistence/nowcast**, locks to the morning balloon and allows drift until launch | Mode P = **past dates**: ERA5 at that hour plus a residual network trained on balloons (`tempest/forecast/modeP.py`). `c1_fit_lagcorr.py` feeds **hourly coherence** (`tempest_weather/coherence.py`), not a nowcast. Day-of-launch conditioning is a *separate* function (`TempestFlightSimEngine.condition_on_observations` / `observe_by_weights`) whose held-out validation (IL-33) is **still to do** | **High**: it describes a capability as if it were validated | A2 |
| 4 | Mode letters C / F / P | Router modes: P, P0, F (0–7 d), F2 (8–15 d), M (weeks 3–6), C. The tool uses named modes `past / recent / week / medium / ai` (`tempest_weather/modes.py`), several of which **fall back and set a flag**. Mode F is trained on archived HRES, tested on **2022 only**, and is the tool default only for 0.75–7.5 days at 14–20 h solar | Medium | D2 |
| 5 | `coherence.py` enforces the ideal gas law and hydrostatic balance | `coherence.py` = Gaussian copula **over hours**. Hydrostatic/gas-law derivation of p, ρ and a lives in `tempest/output/coupled.py` / `atmosphere.py` | Low (wrong file, right idea) | none |
| 6 | Loss = multivariate energy score | Loss = **per-value almost-fair CRPS** + `es_weight = 0.1` × energy score + `step_weight = 0.5` CRPS on height-to-height steps (shear), plus a tail-weighted shear term in p2f. No "spectral / power-law" penalty exists | Low | none |
| 7 | FiLM layers are driven by the context (location, season, forecast) | FiLM scales and shifts the layer norm from the **noise embedding**. An optional context network can *join* the noise embedding (`model.py`, `Generator.__init__`). So the conditioning is noise-first, not context-first | Low | none |
| 8 | Trust/OOD layer widens uncertainty when extrapolating | `trust.py` blends toward the 15-year climatology quantiles. It was **tested and switched off** (FINAL_REPORT §7). There is no active OOD guardrail; out-of-box requests are simply refused | Medium | A6 (needed once the system goes global) |
| 9 | PIT and seasonal recalibration are applied | PIT recal (IL-86) was **mixed, so off**. Seasonal widths exist **for RH and surface only**, behind a flag that isn't exported yet (waiting on the IL-16 stack check) | Medium | section 4 |
| 10 | Shear tails: "violent jet-stream shear never underestimated" | Shear patches (`shear_tail.py`) **did not help, off**. Measured 99.9th-percentile shear is **6–20 % low** (IL-38). What actually helps is the shuffle plus the whole-distribution shear map (IL-91/F-16) | **High** for a rocket | A3 |
| 11 | Analogs blended in from `tempest/analogs/`, `scenarios.py` | `tempest/analogs/` is an empty package. `tempest/forecast/scenarios.py` picks real samples at outcome percentiles; it doesn't search for analogs. Analog/real-ERA5 profiles act as baseline and fallback (README) | Low | D2 |
| 12 | Chronos used to benchmark the AI | Chronos-2 was tried **for forecasting the climate indices**, and lost to ridge | Low | none |
| 13 | "40+ tests" | 49 test files, ~90 tests | Low | none |
| 14 | 1,024 atmospheres "in milliseconds" | Not measured anywhere in the docs | Medium | A7 |
| 15 | Dryden gives "3D eddies every millisecond" | Dryden along a **vertical traverse** (w longitudinal, u/v transverse) on a fine dz grid, plus an optional 1-cos gust. The intensities come from the profile itself | Low | note in A4 |

What Gemini got right and is worth keeping in mind: grid data is smoother than balloons (that is why the station/balloon transfer exists); calibrating each height on its own breaks vertical coherence (Schaake shuffle); and surface gusts at rail exit plus pad soak are real flight drivers.

---

## 2. The real state (from `docs/results/FINAL_REPORT.md`, 2026 Jan–Jun final test)

- The 99 % ranges hold on the untouched half-year (mean |cov99 − 0.99| = 0.0049 against ERA5, 0.0064 against balloons).
- Against the Earth-GRAM-style Gaussian baseline, the system wins clearly on **temperature and surface** (+9 to +25 %) but only **ties or loses on wind** (u 1–5 km −3 % on both truths).
- **T 12–18 km has negative skill** against recent climatology (−0.030 / −0.039) because the target shifted around 2020.
- **Balloon RH 12–18 km coverage is 0.958** and v 12–18 km is 0.977, the weakest cells.
- On per-variable CRPS it doesn't beat E12. Its gains are in coherence, the shear distribution, surface spread, forecast blending and the tool.
- The tail-rate error is ~3–4× nominal (goal 0.2), and that goal is probably out of reach at these sample sizes.

For a rocket, **wind matters most**, and wind is exactly where the system is weakest against a simple baseline. That should drive the priorities below.

---

## 3. What we should actually do

Ordered by value to the end use (Monte Carlo landing dispersion). Each item names its existing ID where there is one and an acceptance test in the repo's own pass-rule language (`compare_headline.py` + `shape_verdict.sh`, seed-spread threshold).

### A1. Decide the altitude ceiling (P0, needs Senai)
- **Question:** what apogee do the target vehicles reach? If it is above 18 km, the tool currently hands the simulator nothing up there.
- **Options:**
  - (a) Stay at 18 km, document it loudly, and make the API **raise** (or return a flagged standard-atmosphere extension) when asked above it.
  - (b) Extend to ~30 km: more pressure levels (ERA5 has levels up to 1 hPa; the current 13-level pull probably stops near 50 hPa / ~20 km, *check*), new heights in `HEIGHTS`, a rebuilt dataset, a retrain, and balloon calibration up there. IGRA soundings often reach 25–30 km, but the sample thins out with height.
  - (c) Hybrid: keep the generator at 18 km and add a calibrated climatological extension from 18 to 30 km, tied to the 18 km values by a copula on the overlap.
- **Recommendation:** (c) first if apogees go past 18 km, because it is cheap and honest. Choose (b) only if stratospheric wind matters for dispersion. For most high-power rockets it barely does, because dynamic pressure up there is low.
- **Accept:** cov99 of balloon u/v/T at 18–30 km within 0.01 of 0.99 in 2024–25, and no change below 18 km.

### A2. Validate day-of-launch conditioning (P0) = IL-33
The code exists (`condition_on_observations`, closed-form Gaussian copula, `inflate=1.5`; `observe_by_weights`, importance resampling). This is the feature Gemini thought was "Mode P", and it is the most useful thing for launch day. It has **no held-out test yet**.
- Test: condition on the surface values plus the lowest N heights of 2024–25 balloons, then score the *unobserved* heights against unconditioned samples.
- Also test a **time lag** (morning sounding 2–3 h before the target hour). That needs `atmosphere_sequence` together with conditioning, which is the real "balloon at 8, launch at 10" case.
- Report the effective sample size for `observe_by_weights`, and tune or justify `inflate=1.5` on calibration years, not on the test.
- **Accept:** CRPS at 0–3 km improves beyond the seed spread, cov99 holds, and ESS ≥ 200 out of a 2,048 pool.

### A3. Fix the wind and shear tails (P0) = IL-38 + current shape stack
Wind is where the system only ties a Gaussian baseline, and shear tails are 6–20 % low at the 99.9th percentile.
- Export the shape stack that already passed (shuffle with 2° templates + whole-distribution shear map, `--post-templates --post-smap`), then **re-export the bundled assets**. Several passed items (F-27 `--wcalib`, F-12 `--modep-sfc`, F-11 `--modep-sta`) are "not re-exported yet".
- Run the int16 tail check (99.9th-percentile shear, float vs int16) before the global store is used for training, so quantization doesn't clip tails.
- Then attack u 1–5 km specifically. It is negative against both truths, so start with diagnosis: stress-table cells by season × hour, and whether the balloon correction under-spreads it.
- **Accept:** 99.9th-percentile shear within 5 % in all bands (IL-38 target), and u 1–5 km skill vs Gaussian ≥ 0 on balloons in 2024–25.

### A4. Downstream proof without the user's simulator (P1) = IL-31 → IL-32
Per-column CRPS isn't what a rocket experiences. Build the small 3-DOF ascent plus parachute descent model (`tempest/downstream/`) and fly it through (a) real 2024–25 balloons, (b) coupled samples, (c) independent-column samples, (d) standard atmosphere with uniform wind, (e) the Gaussian baseline. Start with the M12 tracer-drift proxy because it is trivial.
- Include Dryden on/off and gust on/off so the flight-physics layer is shown to matter, not just assumed to.
- Then add the drift and landing rows to the headline table (IL-32) so every future change is judged on them.
- **Accept:** (b) has the smallest error in 95th/99th drift and landing distance.

### A5. Downrange and hourly coherence: validate what's built (P1) = IL-35/IL-36, Group C
`atmosphere_sequence` and `atmosphere_downrange` exist in `api.py`. Confirm they meet M17: correlation vs lag and correlation vs distance within 0.05 of ERA5, and the 12 h wind-change distribution against 00Z/12Z balloon pairs.

### A6. Out-of-distribution guard before going global (P1, with G3)
Today the box gate refuses out-of-box requests, which is safe. Once the global model serves new places, a refusal won't be enough. Build the DI/AOA flag already planned in G3 (`output/atmosphere.py` `BOX` gate → DI/AOA flag), and widen or flag results based on the leave-one-box-out score for that region. Don't revive `trust.py`'s blend; it already failed.

### A7. Measure runtime (P2)
Time `atmosphere_set(n=1024)` with the numpy engine (cold and warm, pilot site, each mode) and `sample_sobol_batch` with Dryden on. Put the numbers in `tempest_weather/README.md`. If a Monte Carlo of 1,000 runs is CPU-bound on Dryden at `dz_fine_m=2.0`, offer a coarser default.

### A8. Things only Senai can unblock (from ASK_LATER, they gate A-items)
- Push the local commits (ASK_LATER 2), so GitHub reviewers stop reading a stale tree.
- Logger as a scheduled task (ASK_LATER 1): days that aren't logged are gone for good, and that blocks forecast-mode calibration.
- Vehicle limits for go/no-go P(scrub) (ASK_LATER 3).
- Real Earth-GRAM (ASK_LATER 4), the comparison you ultimately want to show.
- Apogee/ceiling answer for A1.

---

## 4. Do NOT do (Gemini implies these are on; they were tested and rejected)

Keep these flags off unless new evidence appears:
- Trust layer blend (`trust.py`)
- PIT recalibration alone (IL-86, mixed)
- Shear patches (`shear_tail.py`) and shear-loss variants
- Seasonal widths beyond RH and surface
- Median shifts (IL-13, IL-72)
- 8-seed ensembles, token generator, driver interactions (F-14, IL-97, far worse)
- Chronos-2 for the climate indices
- Rewriting the architecture as a transformer or diffusion model (Gemini's framing implies MLP+FiLM is a compromise; the measured bottlenecks are data, tails and calibration, not model capacity)

---

## 5. Documentation fixes (D-items, cheap)

An outside reader got the basics wrong, so state them where nobody can miss them:
- **D1**: put a "Scope and limits" box at the top of `README.md` and `tempest_weather/README.md`: heights 10 m–18 km AGL; pilot box only (others refused); hours 06–21 solar; which modes are live vs falling back with a flag; forecast mode tested on 2022 only.
- **D2**: add a mode glossary that maps router names (P, P0, F, F2, M, C) to tool names (`past / recent / week / medium / ai`), with one line each on source, validated period and status. Say explicitly that **Mode P ≠ nowcast** and point to the conditioning API.
- **D3**: in `tempest_weather/README.md`, add a "Validated vs built" column for each output (conditioning, sequences, downrange, Dryden, avionics, soak, thermals). *Built* isn't the same as *tested against balloons*.
- **D4**: either remove the empty `tempest/analogs/` and `tempest/drivers/` and `tempest/past/` packages, or give each one a docstring saying where the logic actually lives. Empty packages invite confident wrong descriptions like Gemini's.

---

## 6. Open questions for Senai

1. Target apogee range? (decides A1)
2. Is day-of-launch use with a morning balloon a real plan? If yes, which instrument and data format (IGRA-like, Windsond, iMet)? (shapes A2's input)
3. Which 6-DOF simulator, and does it need the Sobol interface or just files? (A4, IL-39)
4. Go/no-go limits per vehicle (A8)
