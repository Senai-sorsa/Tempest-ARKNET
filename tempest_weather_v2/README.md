# tempest_weather_v2 (Section 2 build)

Additive package next to `tempest_weather`; it imports `tempest_weather` and changes nothing in it. Built in the order of `docs/plans/SECTIONS_PLAN.md`
(2A flexibility, 2B speed, 2C usage) from `Downloads/tempest_weather_v2_master_upgrade_specification.md`. Not included: 2D validation, the global extension.
Rules: stdlib + numpy only; every module has tests in `tests/`; run them with `PYTHONPATH=. python -m pytest tempest_weather_v2/tests`.

| Module | Spec | State |
|---|---|---|
| `_files.py` atomic writes, checked cache, lock | I1-I3 | done, tested |
| `_net.py` timeouts, retries, rate limits, offline, resumable download | N1-N3 | done, tested |
| `elevation.py` lookup (USGS, Open Topo Data, Open-Meteo, offline DEM, cache) | 0.1, Part 4 | done, tested, on `_net` / `_files` |
| `readers.py` `Atmosphere`: 10 m float32 tables, frame/units/reference/direction, above_top policy, pad node, anchor, OpenRocket CSV, schema normaliser | F7, S2, F12, F3, F10 | done, tested; scalar lookups 0.7 us (original readers 3-6 us), 0.08 us per altitude vectorised; real flight_sim flights agree with the original readers to 0.45 m apogee |
| `timeutil.py` `Window`: local wall-clock times, uniform / triangular / union-of-ranges launch times, 06-21 h solar cut, exclusions, relative times | 0.2, I-5, I-6 | done, tested (tzdata needed on Windows) |
| `weather_calc.py`: altimeter setting + exact inverse, MSLP, density altitude, dew point, drift-equivalent uniform wind, max shear, jet wind, degree-4 IGRF declination | 1.1-1.3 | done, tested (declination within 3 deg at 7 cities) |
| `names.py` plain names, units, aliases, typo suggestions, quantity parsing | I-3 | done, tested |
| `sites.py` + `data/sites.toml` registry, user sites, tz guess, declination | 0.1, I-5 | done, tested |
| `results.py` `Weather` (table, attributes in chosen units, RASAero / OpenRocket exports) | I-2, 1.5 | done |
| `stats.py` best-fit distributions + tail check; `Coupled` (whole_sample, gaussian_copula, t_copula with exact conditional Student-t) | 2, 3 | done, tested |
| `launch.py` `Launch` (immutable, lazy cached pool; `weather()` incl. percentiles / RAS profiles, `distribution()`, `couple()`, `atmospheres()`, `engine()`, `observe()`, `save()` / `load()`, trust line, provenance) | 1, 2, 3, 4, 5, I-1, I-4, I-7, I-8 | done, tested on the real NM/TX assets (11 tests); `sounding="auto"` waits for R2 |
| `cli.py` + `__main__.py`: `tempest weather|distribution|couple|atmospheres|variables|sites|doctor|selftest` | I-9, P-3, P-11 | done, tested (`tests/test_roughness_cli.py`); `--metar` option conditions on a METAR |
| `roughness.py` + `data/z0_table.csv`: directional z0 from a land-cover map (AERSURFACE method), sector / season lookup, fallback 0.03 m flagged | R1 | done, tested; the NLCD map itself is not shipped (build with `build_sector_map`); the class table is an approximate stand-in |
| `metar.py` METAR / SPECI parser; `Launch.observe_metar(text)`; `observe(station_pressure=, altimeter=)`; `Launch(era5_store=)` with a loud fallback warning | R2 (offline half), validation findings | done, tested (82 tests in the package) |
| `obs.py` nearest stations, IEM METAR fetch (through `_net`), age / distance / elevation weights; `Launch.observe(age_hours=, distance_km=, elevation_diff_m=)` (soft Gaussian update) and `Launch.observe_latest()` | R2, IL-156 | done, tested offline (weights from GW-1: decay time 6.3 h; distance and elevation scales are assumptions, flagged) |

## What the range means, and what it does not (flight-sim test, 2026-11-08)

- The sampled atmospheres give the uncertainty of the **atmosphere only**. In the flight-simulator rerun on the three flights that could be tested (`FlightSIM&Validation with Tempest-ARKNET.md`, section 12) the vehicle error (5-8 % over for two rockets, 4 % under for the third) was 2-4 times the whole atmosphere effect, and the measured apogee lay outside the whole sampled apogee distribution in 8 of the 9 flight-and-scenario pairs of the first three variants (climate, past, past plus a pinned station observation; 18 of 20 over all seven variants). Add your own vehicle uncertainty before reading the spread as an apogee range.
- For a specific launch day use `past` mode (any date 1990-2025, needs the ERA5 store), a forecast, or `observe_latest()` / `observe_metar()`. Climate mode is a prior: an unusual day (strong wind, heat wave) lies in its tails (the Juno III launch wind was at the 99th percentile of the climate distribution).
- Of the atmosphere inputs, the wind between 0 and 200 m moves apogee most after the pad air itself; the tool's ground wind is the part to improve and to check against a pad anemometer if you have one.
- **Hybrid use** (section 13 of the validation file): `Atmosphere(samples, k, air="standard")` keeps the 1976 standard atmosphere at the pad elevation (optionally `delta_t_k`) and takes only the wind from Tempest; `perturbation=dict(z, east, north, up)` adds turbulence or gust fields. On the three testable flights this hybrid had the lowest apogee error (4.89 % against 6.15 % for the basic standard atmosphere and 5.80 % for the full Tempest atmosphere), partly because the standard air offsets a simulator bias; it is not shown to be more accurate than the full atmosphere.
- **Total-uncertainty Monte Carlo** (`montecarlo.py`): `run(simulate, Launch(...).atmospheres(n), VehiclePriors(drag_scale=("lognormal", 0.05), ...), n, seed)` samples atmospheres AND vehicle scale factors (Latin hypercube) and returns the apogee distribution, its 90 % interval, the rank of a measured value and the first-order variance shares; `calibrate_vehicle_sigma(errors_pct, atmosphere_sd_pct)` turns past flights into the vehicle share of the error (flagged unreliable below 5 flights). The atmosphere pool alone is the uncertainty of the air only.
- `observe_hrrr()` anchors the ground wind to HRRR 10 m wind; its weights were fitted at airport stations that HRRR very likely assimilates, so the benefit is optimistic for a remote pad.
