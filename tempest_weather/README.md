# tempest_weather

A probabilistic atmosphere for the pilot box (31-34 N, 108-101 W, West Texas / New Mexico) from a **place and a time**. Wind, temperature, humidity at 44 heights from
10 m to 18 km above ground, surface values, pressure, density and speed of sound derived from each sample, vertical wind, gusts. Needs **numpy only**
(`xarray` + `zarr` are optional, only for answering past dates from a local ERA5 store).

Copy this folder into another repo (the `assets/` folder, about 75 MB, is not in git: copy it too, or re-create it with `python -m tempest.export_tool` in the main repo).
The folder checks `assets/manifest.json` hashes on first use and refuses files that do not match.

## The four calls

```python
from tempest_weather import values, distribution, couple, atmosphere

# 1. best estimates, in the order asked
r = values(32.99, -106.97, "2027-06-16 09:00", ["t2m_c", "sp", "wind_speed@100", "wind_dir@100"])      # r["values"], r["units"], r["mode"], r["quality"]

# 2. distributions for Monte Carlo: type + parameters (or a quantile table) per variable
d = distribution(32.99, -106.97, "2027-06-16 09:00", ["t2m_c", "wind_speed@100", "rh2m_frac", "gust10"], setting=0)
d["variables"]["wind_speed@100"]   # {"type": "weibull", "params": {"shape": ..., "scale": ...}, "units": "m/s", "note": ...}

# 3. coupling: draws that keep the variables consistent with each other
c = couple(32.99, -106.97, "2027-06-16 09:00", ["t2m", "sp", "wind_speed@100"], method="whole_sample")
idx, rows = c.draw(500)            # rows are real whole atmospheres; c.spec() describes the coupling

# 4. single-value simulator inputs at points along the worst-to-best order of the day's atmospheres
atmosphere(32.99, -106.97, "2027-06-16 09:00", percentiles=(15, 50, 85), extras=("gust10", "rho_sfc"), elevation=1400)
```
Terminal: `python -m tempest_weather atmosphere --lat 32.99 --lon -106.97 --when "2027-06-16 09:00" --elevation 1400 [--percentile 25 50 75] [--extra gust10] [--format text|toml|json]`;
`python -m tempest_weather values ... --vars t2m_c sp`; `python -m tempest_weather variables` lists every variable name.

**Time.** A string without an offset is **local solar time** at the longitude (no timezone database is needed); add an offset (`+00:00`, `-06:00`) for an exact instant. Only 06-21 h solar are answered.
**Percentiles** of `atmosphere` run along **flight conditions from worst (0) to best (100)**, not along any single variable: 15 is a bad but plausible day, 85 a good one. The ranking score
(`ranking.py`) is a placeholder weighting of wind, shear, gust and air density until your go/no-go limits exist; pass `score_fn=` to use your own. The wind in the output is the 100 m wind
(as `Weather_to_JARVIS_inputs.py` uses for `UniformWind`); `--format toml` writes the same layout as that script.

## Settings of `distribution` and `couple`

| setting | distribution types | model error |
|---|---|---|
| 0 | standard (normal, lognormal, gumbel, weibull, beta; empirical is returned, and says so, where none fits the tails) | included |
| 1 | standard | not included |
| 2 | empirical (a quantile table, dense in the tails) | included |
| 3 | empirical | not included |

"Model error included" = the full uncertainty set: the four generator members, drawn climate indices (ENSO, QBO, warm water volume), the range-calibration map (so the 99 % range holds about
99 % of outcomes on held-out years). "Not included" = indices at their expected values and no range map: narrower, a description of the typical weather, not a safety margin. For a past date the
settings with error add the balloon-fitted ERA5 error; without error the answer is the ERA5 value itself (`type: "constant"`). One file per type in `distributions/`, one per coupling type in `coupling/`.

## Modes (chosen from the time distance to now; answer carries `mode`, `source`, `quality`)

| mode | when | state |
|---|---|---|
| `past` | more than ~6 days ago | **works with a local ERA5 store** (`era5_store=` or env `TEMPEST_ERA5_STORE`, the pilot profiles zarr): ERA5 for that hour + a network trained on balloons (median error ~6 % below raw ERA5) + calibrated range |
| `recent`, `week`, `medium` | now to 46 days ahead | **not available yet**: live forecasts need a verification history that is still being collected; the call falls back to `ai` and says `fallback-mode` in `quality` |
| `ai` | beyond, and the fallback | the climate generator, calibrated; skill over "what is normal for this date" is small (a few per cent) by nature, the value is honest ranges and coherent profiles |

## Honest limits
- Outside the pilot box the calls raise an error; they never extrapolate.
- Month-ahead weather is not predictable: `ai` mode is a calibrated climate-with-trend distribution, not a forecast.
- Flight-score weights, the 100 m wind as the single wind, and gust profile above 10 m are placeholders/choices, marked in the code.
- Soak history and thermals (`w_sigma`, `w_turb`) are not included here (soak needs a large hourly library; thermals need sensible heat flux data), see `docs/agent/ASK_LATER.md` in the main repo.
- Everything was tested on 2024-25 ("development" years, used for many decisions); the final test is 2026 January-June.
