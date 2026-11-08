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
