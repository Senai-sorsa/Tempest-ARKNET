# tempest_arknet — launch-site weather from Tempest-ARKNET

Mean atmosphere, standard deviations and Monte Carlo atmospheres above a launch
site at a given local time. Same interface, command line and CSV files as the
`earthgram` tool in `dynamics/tools/weather/earthgram`. The engine is Tempest-ARKNET
(`tempest_weather.api.atmosphere_set`), not NASA Earth-GRAM.

## Setup

- This folder sits in the Tempest-ARKNET repo, next to `tempest_weather/` and its
  `assets*/` folders (the trained models). Nothing else to install: `uv sync` once.
- Only the trained regions are answered: **NM/TX 31–34 N, 108–101 W** and
  **Denver 38–40 N, 106–104 W**. Anywhere else raises an error; nothing is extrapolated.

## Use

```python
import tempest_arknet as ta     # run from the Tempest-ARKNET folder

site = ta.LaunchSite("West TX", lat=31.024, lon=-103.6616, elev_m=900)

prof = ta.profile(site, "2026-06-15 13:00", tz="America/Chicago", step_m=250)
prof.mean           # alt_m, temp, p, rho, u, v, rh (+ _sd for each), speed, speed_sd, sos, dir_from
prof.info           # mode (past / forecast / ai), source, quality flags
prof.sigma(-3)      # mean - 3 sd for each quantity (a quick bounding case)
prof.at(3000)       # mean, interpolated to 3000 m MSL

mc = ta.monte_carlo(site, "2026-06-15 13:00", tz="America/Chicago", n=500, seed=1234)
mc.runs             # run, alt_m, temp, p, rho, u, v, speed, dir_from, w, sos, rh
mc.run_profile(17)  # one atmosphere, e.g. for one dispersion sim
mc.percentiles([5, 50, 95])   # alt_m, temp_p5, temp_p50, temp_p95, ...

ta.launch_window(site, "2026-06-15", "America/Chicago", hours=range(9, 18))
ta.openrocket_wind_csv(prof.mean, "wind.csv")
```

Command line (from the Tempest-ARKNET folder, with its `.venv` active):

```bash
python -m tempest_arknet -h
python -m tempest_arknet --lat 31.024 --lon -103.6616 --elev 900 --time "2026-06-15 13:00" --tz America/Chicago
python -m tempest_arknet ... --csv table.csv            # the printed table as a CSV
python -m tempest_arknet ... --mc 500 --out results     # mean_profile, openrocket_wind, monte_carlo_runs, percentiles CSVs
```

A profile (1024 atmospheres) or 500 Monte Carlo atmospheres take about 5 s.
Example plot: `python tempest_arknet/examples/plot_monte_carlo.py`.

## Differences from earthgram

- **Top altitude:** Tempest stops 18 km above the ground, so `--top` defaults to
  (and can't go above) `elev + 18000` m. Earth-GRAM goes to 30 km and beyond.
- **Mean and sd** are statistics of `n` sampled atmospheres (`--n`, default 1024),
  not a separate climatology table. With `--mc`, the mean is that of the runs.
- **Source depends on the date** (`info["mode"]`, printed under the header): ERA5
  plus a balloon correction for past dates (needs a local ERA5 store), the IFS
  forecast 0.75–7.5 days ahead (needs network), otherwise the calibrated climate
  generator. `--mode` forces one. Earth-GRAM is always monthly climatology.
- **Extra columns:** relative humidity `rh` (%), and `w` (vertical wind) in each run.
  There is no `w_sd`.
- **Ground row:** 2 m temperature and humidity and surface pressure; the wind below
  the lowest model height (10 m) is the 10 m wind.
- **No GRAM inputs:** extra keywords go to `atmosphere_set` instead (`mode=`,
  `era5_store=`, `assets=`, `predicted=`).

## What the numbers mean

- **Units:** SI. Altitude in m above MSL; u is toward east, v toward north; `dir_from`
  is the direction the wind blows from, in degrees clockwise from north.
- **Time:** local time with `--tz` (IANA name), converted to UTC before Tempest sees it.
- **Monte Carlo:** each run is a whole, vertically coherent atmosphere drawn by
  Tempest (no separate perturbation model). `sigma(k)` shifts every quantity
  independently and is not a physically consistent atmosphere.
- **Between model heights** (44 heights, 10 m–18 km above ground) values are linear,
  pressure and density log-linear.

## Tests

```bash
python tempest_arknet/tests/test_tempest_arknet.py
```

The offline tests use a synthetic sample set. The live tests run Tempest and are
skipped when no asset set is present. The repo's `pytest` run (testpaths = `tests`)
does not pick these up.
