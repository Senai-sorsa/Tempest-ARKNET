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
