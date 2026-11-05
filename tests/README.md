# tests

`python -m pytest -q` (about 4 minutes; never run it while a scoring job is running). Groups: data pipeline and indices, generator and calibration, flags-off guard
(`test_flags_off.py` + `golden_train.json`: a tiny fixed-seed training run must reproduce the numbers recorded before the Phase 2 edits), Phase 1-4 modules
(logger, thermo, trust, joint, coupled files, gust, thermals, soak, index forecast, scenarios, router, Open-Meteo client, ensemble conversion). No test touches the network or the 2026 data.
