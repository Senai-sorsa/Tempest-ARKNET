# Phase 5: the query tool (`tempest_weather/`), reworked from the user's vision

Written 2026-11-05. Source of the requirements: the user's own note, copied unchanged to `Code-Modifications/phase5_inputs/original_tool_plan_from_downloads.md`
(it describes the vision in plain words). This file adjusts it to the system as it now stands and keeps the user-facing calls as written.
It replaces `docs/TOOL_PLAN.md` for modes 1-3 and for the build order; steps T1, T5, O2-O8 and C3-C6 of PHASED_PLAN section 4 are folded in below.

## 1. What the user asked for (their words, condensed)

- One folder, small enough for git, that can be copied into another repo (`flight_sim` / `dynamics`), no `import tempest` needed.
- **Call 1, values:** given a location and a time, return the requested figures in the order asked.
- **Call 2, distribution** (for Monte Carlo): return the distribution *type* and the data to build it; one file per distribution type in the folder; optionally
  empirically fitted distributions. Four settings:
  - 0 standard distributions that account for model error (future dates);
  - 1 standard distributions without the model-error part;
  - 2 empirically fitted distributions, with model error;
  - 3 empirically fitted, without model error.
- **Call 3, coupling** between requested parameters: the most effective coupling for this design, or several types chosen by a setting (like call 2).
- **Call 4, `atmosphere`** (also a terminal command): for a date and place, the atmosphere inputs for a given percentile of **flight conditions from worst to best**
  (not percentiles of each variable). Default percentiles 15, 50, 85. The default output is what RAS (the simulator input) takes: single values, easy to read
  and paste. Extra parameters on request, never series.
- Compatible in style with `flight_sim`; gusts and other things the sim lacks yet are fine to include for the future.
- The data getter keeps our modes: (a) past: what already exists; (b) now / very recent: corrected predictions; (c) within about a week: corrected predictions;
  (d) longer term: recent data and predictions used to correct long-range forecasts; (e) beyond a threshold: the AI alone.

## 2. What the system can honestly deliver per mode (state on 2026-11-05)

| Mode | Lead | Built | Source / accuracy | Gap |
|---|---|---|---|---|
| `past` | before now | yes (Phase 4.4) | ERA5 for that hour + residual network and range map, hybrid; 6 % below raw ERA5 median error vs balloons, CRPS 5.5 % below the old station correction | needs ERA5 access at query time (local zarr on the dev machine; online Earthmover store or Open-Meteo otherwise); 21-level CDS data not yet in |
| `recent` | -5 to 0 days | converter only | live ensembles converted to our heights, uncorrected | no verification history yet (logger started 2026-11-05) |
| `week` | 0-7 days | converter only | same | same; flagged `uncalibrated` in every answer |
| `medium` | 8-46 days | EC46 archive growing | ensemble hand-over blended to the AI by the router (smooth weights) | no true upper-air lead history exists (probe); weeks 3-6 add nothing measurable over the AI until the archive grows |
| `ai` | beyond | yes | p2f generator + calibration + ridge index forecast; skill15 +0.028 ERA5 / +0.008 balloons | month-ahead skill stays close to climatology by nature |

Every answer carries `mode`, `source` and a `quality` list (`nominal`, `uncalibrated`, `stale-source`, `fallback-mode`) so a degraded answer is never silent.
Honesty rule: the tool does not claim a forecast skill it has not measured; "uncalibrated" modes return ranges widened by a stated factor and say so.

## 3. Folder layout (self-contained, numpy only)

```
tempest_weather/
  __init__.py        values, distribution, couple, atmosphere, __version__
  __main__.py        terminal: python -m tempest_weather atmosphere --lat --lon --when [--percentile 15 50 85] [--extra ...] [--format text|toml|json]
  api.py             the four functions
  modes.py           lead -> mode, settings, quality flags
  engine.py          numpy forward pass of the exported generator, range calibration, w-head, gust, soak (parity-tested against tempest/)
  distributions/     base.py (registry) normal.py lognormal.py gumbel.py weibull.py beta.py empirical.py  - one file per type: fit, ppf, sample, spec
  coupling/          whole_sample.py gaussian_copula.py  - one file per coupling type
  ranking.py         flight-condition score, worst-to-best ordering, percentile pick
  outputs.py         RAS / JARVIS TOML / text / json formatting and units
  sources/           era5.py (optional xarray/zarr/icechunk or a local store), openmeteo.py (stdlib), indices.py (ONI/QBO/WWV), cache
  assets/            weights.npz calib.npz whead.npz gust.npz manifest.json  (kept out of git, fetched/copied; about 50 MB)
  README.md
```
Export is done by `tempest/export_tool.py` from the trained checkpoints; a parity test (`tests/test_tool_parity.py`) checks the folder reproduces `tempest/` outputs within 1e-5
for the same inputs and noise.

## 4. The four calls (user-facing)

```python
from tempest_weather import values, distribution, couple, atmosphere

values(lat, lon, when, variables=("t2m", "sp", "rh2m", "wind_100m", ...), mode=None)        # ordered dict, plus mode/source/quality
distribution(lat, lon, when, variables, setting=0, n=1024, kind="uncertainty")              # {name: spec}, spec = {"type", "params", "data", "units"}
couple(lat, lon, when, variables, method="whole_sample" | "gaussian_copula", setting=0, n=1024)   # coupling object: draw() gives rows, jointly
atmosphere(lat, lon, when, percentiles=(15, 50, 85), extras=(), units="ras")                # list of atmospheres from worst-case-ish to best
```
- `variables` are names from one registry (`t2m`, `sp`, `rh2m`, `u@100`, `v@100`, `wind_speed@100`, `wind_dir@100`, `T@z`, `RH@z`, `rho@z`, `gust10`, `w@z`, `shear@z1-z2`, `T_soak` ...);
  anything not in the registry raises a clear error naming the valid ones.
- **Distribution types** (one file each): `normal`, `lognormal`, `gumbel` (gusts, extreme wind), `weibull` (wind speed), `beta` (humidity as 0-1), `empirical` (quantile table, the
  data to rebuild it). Each file has `fit(samples)`, `ppf`, `sample`, and `spec()` returning the plain dict above. Selection: settings 0/1 choose a *standard* type per variable by a fixed rule
  (physical support first: humidity -> beta, wind speed and gust -> weibull/gumbel, others -> normal, strictly positive -> lognormal) checked by a goodness-of-fit test on the samples
  (kept only if it beats the empirical fit's tail error by a stated margin, else empirical is returned and flagged); settings 2/3 always return `empirical`.
- **Model error** (settings 0 and 2): the uncertainty kind: generator members' disagreement, drawn index values, the range-calibration map, and the mode's own error (past: balloon-fitted ERA5 error;
  forecast modes: widened by the tested factor). Settings 1 and 3 (no model error): the predicted kind: indices fixed at expected values, no range map; for `past` the ERA5 value itself with no error part.
- **Coupling** (call 3): `whole_sample` (default; the most faithful, it keeps the real joint structure, shear, T-density, thermals with wind; draws are row indices into one set of whole atmospheres) and
  `gaussian_copula` (rank correlations plus the marginals of call 2, for sims that need a parametric joint; known to lose skew and extremes, documented). `setting` has the same 0-3 meaning as call 2.
- **atmosphere / ranking** (call 4): every sample gets a **flight-condition score** (higher = worse): default = a weighted sum of standardised mean wind speed 0-3 km, maximum shear 0-5 km, 10 m gust,
  and low density (high density altitude); the weights and limits are settings and will take the user's go/no-go limits when they exist (ASK_LATER 3). Samples are sorted worst to best; percentile `p` picks the sample at
  position p % along that order (0 = worst, 100 = best), so 15 is a bad but plausible day and 85 a good one. Within the tool the pick is an actual whole sample (real internal consistency), never a mix.
- **RAS-ready output:** single values from the picked sample: launch site latitude, elevation, temperature (degC, also degF), pressure (Pa, also hPa/psi), relative humidity (0-1), wind east / north (m/s) and wind speed
  / direction from the 100 m wind (the one `Weather_to_JARVIS_inputs.py` uses for `UniformWind`), plus extras on request (gust, density, speed of sound, wind at heights as single numbers). Formats: aligned text for reading and pasting,
  `site_<date>.toml` in the same layout as `dynamics/tools/weather/Weather_to_JARVIS_inputs.py`, and json.

## 5. Build order (each step: code behind a clear name, tests, a row in PLAN.md)

| Step | Content | Check |
|---|---|---|
| 5.1 | `tempest/export_tool.py` + `tempest_weather/engine.py` (generator forward pass, calibration, w-head, gust, soak, thermo) | parity test 1e-5 on samples; folder imports with numpy only |
| 5.2 | `distributions/` (six types) + `coupling/` (two types) + registry of variables | unit tests: fit/ppf/sample round trips; coupling reproduces correlations and marginals |
| 5.3 | `ranking.py` + `outputs.py` + `atmosphere()` + terminal command | hand-checked cases; percentile order test; TOML loads in `dynamics` layout |
| 5.4 | modes: `ai` (full), `past` (ERA5 + mode P), `recent/week/medium` (ensemble conversion, router blends, flagged) | per-mode tests with recorded fixtures; fault injection (API down -> fallback + flag) |
| 5.5 | README, scratch-repo test (copy the folder, only numpy installed), operations: freshness flags, bundle manifest with hashes, health checks | copy test |
| 5.6 | flight-sim readers (C3/C4/C6): `TempestWind` / `TempestAtmosphere`-style readers as examples in the folder docs; sorting by `stratum_key` for one LHS dimension; landing-scatter end-to-end test is described, run only if a vehicle file is supplied | examples run on the demo file |
| 5.7 | validate against the user's goal: distributions for sim validation, coverage on the held-out years through the tool (same numbers as `score.py` within noise) | table in PLAN.md |

Operations O2-O8 (snapshots, extracts, health reports, release process) are scaled to what exists: a model release folder with `manifest.json` and hashes, the freshness rule (<= 12 h nominal, 12-36 h stale, > 36 h live),
the health check script over the logger archive, and a runbook in `tempest_weather/README.md`. Scheduled cloud jobs and shared stores need accounts: ASK_LATER.
