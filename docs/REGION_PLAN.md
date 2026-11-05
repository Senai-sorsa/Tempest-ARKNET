# Where and when the system answers, and how it becomes adjustable to other places (checked 2026-11-05)

## 1. What the check found (scripts/check_scope.py, standalone tool, 68 cases)
| Question | Result |
|---|---|
| Any place in the trained box (31-34 N, 108-101 W)? | Yes: a 5 x 5 grid over the box, all four corners: answers, finite and physical. |
| Any place in North America? | **No. Only the pilot box is trained.** Denver, Phoenix, Las Vegas, Dallas, Miami, Seattle, Toronto, Mexico City and Anchorage are refused with a clear message ("outside the trained area ... other regions need their own assets"). Nothing is guessed outside. |
| Any date in the future? | Yes, to the year 2100 (checked 2026-12, 2027, 2030, 2040, 2060, 2100). Within 7.5 days at 14-20 h solar the answer comes from the IFS forecast (mode F, live Open-Meteo); beyond that from the generator with the index forecast (ONI, WWV, QBO; beyond 12 months those are climatological). The generator extends a straight-line year trend, so the temperature rises about 0.04 K per year (July, 15 h: 285.3 K at 2 km in 2024, 286.0 in 2027, 288.8 in 2100) and humidity falls (RH at 3 km 58 % in 2027, 43 % in 2100). Since 2026-11-05 the tool flags "year-trend-extrapolated-N-years-beyond-the-training-data" beyond 5 years and adds "-unreliable" beyond 25. |
| Any hour of the day? | **No.** Solar hours 06-21 only (the dataset was built for daylight launches); 22-05 h are refused with a message. |
| Any past date? | Only with a local ERA5 store (past mode); otherwise the generator answers and says "past-source-not-available". |

## 2. What is hard-coded to the pilot box (audit)
Found by searching for the box, the grid shape (13 x 29 = 377 points) and the two balloon stations:
- `tempest/ingest/fetch_earthmover.py` (box, 0-360 longitudes), `tempest/ingest/fetch_igra.py` and `tempest/calibrate/station.py` (two IGRA stations with launch heights), `tempest/ingest/fetch_asos.py`, `tempest/gust/model.py` and `scripts/gust_check.py` (two ASOS sites), `tempest/profiles/to_heights.py` (chunking 29), `tempest/profiles/surface_hourly.py` (377), `scripts/gust_check.py` / `scripts/soak_check.py` (point-index formula), `tempest/ingest/arco_fill.py`, `wb2_fetch.py` and the notebooks (box constants), `tempest_weather/api.py` and `_core` (stations for mode P, gust sites), `tempest/forecast/modeP.py` (station list), `tempest/scoring/sonde.py` (station list).
- Done 2026-11-05 (R-1): `configs/region.toml` and `tempest/region.py` (box, step, grid shape, point index, stations, ASOS sites; environment variable `TEMPEST_REGION`); `fetch_earthmover`, `gust_check`, `soak_check` read it; the tool and the atmosphere builder take the trained area from the grid they carry (assets), not from a constant; the export manifest takes the area from the grid. The pilot values are unchanged (test_region.py).
- Still to move onto the region file (R-2): the station dictionaries (`station.STATIONS`, `ELEV`, `modeP`, `sonde`), the ASOS list in `fetch_asos`, `gust.model.SITES`, the 29 / 377 constants in `to_heights.py` and `surface_hourly.py`, the box constants in the extractors and notebooks. The station correction must also handle more than two stations (R-3).

## 3. What "any place in North America" takes (estimates, to be confirmed by a dry run)
| Item | Pilot now | North America (about 20-55 N, 130-60 W) |
|---|---|---|
| Grid points at 0.25 deg | 377 | about 39,000 (105 x). A 1 deg lattice: about 2,500 points (6.8 x); 2 deg: about 640 |
| Profile store (44 heights x 4 variables, hourly, float64) | 158 GB | not feasible at full resolution; a 1 deg lattice, 6-hourly, float32: about 180 GB; 3-hourly 2 deg: about 90 GB. The generator is conditioned on latitude, longitude and elevation, so training on a lattice generalises to the points between (to be tested on held-out points) |
| Training rows | about 7.8 M (6 GB) | about 15 M rows with fewer times per point (12 GB); 2-3 x the training time and a larger network (width 1024) |
| ERA5 extraction | Earthmover store, about a day | the same store, reads scale with the area (about 100 x the pilot unless only needed chunks are read); alternative: ARCO-ERA5 in Colab (one global chunk per hour, about 0.5 GB per hour read inside Google: about 25 TB for 6-hourly 1991-2025, several sessions) |
| Balloon stations | 2 (IGRA) | about 80 US / Canada / Mexico stations; the station correction needs distance blending over several stations (removes the Voronoi seam, F-20) and per-climate pooling |
| Calibration | one range map per variable x height band | one map is probably wrong for coast vs desert vs mountains: maps per climate zone or conditional on the spread (to be tested on held-out regions) |
| Verification | balloons at 2 stations | leave-one-region-out tests (train without a region, test on it) |
| Forecast mode F | trained for the pilot box, 17 h solar | retrain with the forecast archive over the new region (WeatherBench2 HRES is global: one pull, box = the region) and the diurnal pull (ASK_LATER 8) |
| Tool assets | one set (75 MB) | one asset set per region or one set for the lattice; the tool picks the region from the query location and refuses outside all of them |

## 4. Plan (group R in `Code-Modifications/AUTOPILOT.md`)
R-1 region file (done) -> R-2 move the remaining constants onto it -> R-3 station correction for many stations with distance blending -> R-4 region-parameterised extractors and notebooks -> **R-5 portability dry run**: a small second box (2 x 2 degrees, two years, tiny model) built end to end with only `configs/region.toml` changed, then asked through the tool; it proves the pipeline is adjustable -> R-6 the North America plan (lattice choice, data pulls, training, held-out-region tests): needs the user for the Colab data pulls, so it is listed in ASK_LATER and not started unattended -> R-7 tool region registry (several asset sets, pick by location, refuse outside) -> R-8 night hours: build the dataset for all solar hours and retrain (the 22-05 h refusal goes away) -> R-9 flag and bound the far-future trend (a hinge or a damped trend, tested against the CMIP-style warming rate), instead of the straight line.
