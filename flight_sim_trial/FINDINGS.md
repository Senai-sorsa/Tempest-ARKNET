# Flight-sim trial: Tempest atmospheres vs the standard atmosphere (2026-11-08)

**This whole folder is deletable** (`rm -rf flight_sim_trial`). Nothing in the project imports it. It is untracked by git and contains a nested clone (`src/`), so never `git add -A` while it exists.

## What was done
- Code: a clone of `github.com/tamusrt/flight_sim` `main` (commit 93cb8c9, 2026-11-06) in `src/`, with its own virtualenv `src/.venv` (the project `.venv` was not touched). Your local copy at `C:\dev\flight_sim` is checked out on `JARVIS-TRUE-VALIDATION` and its `main` is older than GitHub's; I used the newest GitHub `main` (same `AtmosphereModel` / `WindModel` interfaces). Re-run against the local copy if you want.
- Rocket: the repo's own example, Sol Invictus on a Loki M3464 off a 17 ft rail at Spaceport America (32.99 N, 1400.6 m pad), plus `dummy_light/` (same rocket, dry mass 9 kg instead of 17 kg).
- Scenarios (`experiment.py`): **S0** the plain standard atmosphere, no wind (the simulator's defaults); **S1** the careful conventional setup: standard atmosphere scaled to the site's median surface temperature, pressure and humidity (the simulator's RASAero-style option) plus one uniform wind from the median 10 m wind; **S2** 200 atmospheres from the Tempest tool (`mode="ai"`, climate distribution for 2025-06-24, pad elevation pinned to 1400.6 m), one coupled profile (T, p, RH, u, v, w) per flight through `TempestAtmosphere` / `TempestWind`.
- Cases: 14:00 local (20 UTC), 08:00 local (14 UTC), and the light rocket at 14:00. Real-data check: `check_vs_balloons.py` (236 late-June 00 UTC soundings at Santa Teresa NM, IGRA, 2011-2025). Elevation check: `elev_sensitivity.py`.
- Speed: the tool makes 200 atmospheres in 0.3 s; the simulator flies one rocket in about 0.6 s, so a 200-flight Monte Carlo takes about 3 minutes.

## Results (apogee above the pad, m)
| Case | S0 plain standard | S1 scaled standard + wind | S2 Tempest median (p5-p95) | S0 → S2 |
|---|---|---|---|---|
| 14:00 local | 3562 | 3710 | 3719 (3685-3751) | **+157 m, +4.4 %** |
| 08:00 local | 3562 | 3635 | 3690 (3658-3718) | +128 m, +3.6 % (S1 → S2 +55 m) |
| light rocket, 14:00 | 3854 | 4023 | 4010 (3977-4041) | +156 m, +4.1 % |

- The plain standard day is **outside the whole Tempest distribution** (0th percentile of apogee in all three cases): it is 28 K too cold at the pad in the afternoon (279 K vs 307 K) and 10 % too dense (1.069 vs 0.97 kg/m3). This is the main effect.
- Apogee responds to density as it should: correlation with pad air density -0.81 (afternoon) and -0.67 (morning); a 9 % lower density gives about 4 % higher apogee.
- The careful S1 setup recovers most of that in the afternoon (within 9 m of the Tempest median) but misses 55 m in the morning (2nd percentile): a scaled standard profile cannot represent the morning inversion and the warmer air above it.
- Landing drift: S0 has no wind and still lands 742 m north (the rail points north). Tempest gives 517-957 m with a clear east-west spread (sd 140-180 m; 90 % range up to 1150 m in the morning), driven by winds aloft (maximum along the path 8-9 m/s, S1 has 0.6-2 m/s).
- The atmosphere-driven apogee spread is only sd 20 m (0.5 %). For this class of rocket the atmosphere distribution matters for the mean shift and for drift, not for apogee scatter.

## Do the Tempest results make sense? (reality check against balloons)
Yes, mostly. Real soundings (Santa Teresa NM, 15-30 June, 00 UTC, n = 236) against the tool's range for the same place and hour:
- **Temperature:** 85-94 % of the real values fall inside the tool's p5-p95 (ideal 90 %) and 95-98 % inside p1-p99 (ideal 98 %); median bias at most 0.8 K.
- **Near-surface lapse rate:** 25.0 K/km (balloons) vs 25.3 K/km (tool) between 10 and 50 m, 20.0 vs 21.1 and 16.0 vs 14.2 above it. The strongly superadiabatic layer that looked suspicious is real.
- **Surface temperature:** tool 29.9 / 36.9 / 41.6 C (p5/p50/p95) vs balloons 29.2 / 36.0 / 39.4 C.

## Flaws found (ordered by how much they matter)
1. **Wind spread is too narrow and the lower winds are a little weak.** Real u falls inside the tool's p5-p95 only 80-86 % of the time (ideal 90); the tool's standard deviation is 15-25 % below the balloons' (u 0-1 km: 4.5 vs 5.6 m/s); real wind speed median is 1.0-1.5 m/s above the tool's below 3 km. Effect: the drift spread is understated. Worth a targeted fix (wind spread calibration at 0-12 km, hour-specific).
2. **Pad elevation.** The tool's own lookup puts the pad at 1493.5 m (grid-cell elevation); the pad is 1400.6 m. If not pinned, the pad pressure is 0.87 kPa (1 %) too low and the atmosphere is shifted 93 m (apogee +5 m for this rocket, small only because the rocket is insensitive). Fix = the elevation lookup of Section 2C, and a user-given pad elevation must win. The simulator never calls `TempestAtmosphere.anchor`, so a mismatch is silent: the reader should warn when the first request is more than 10 m below its lowest node.
3. **Upper-air temperature and humidity (minor):** coverage 85-87 % at 6-18 km (ideal 90 %), a -0.8 K bias at 12-18 km, and balloons are 2-4 %RH moister at 3-12 km.
4. **The comparison is climate, not forecast.** `mode="ai"` gives the climatological spread for that date and hour. A flight-day forecast would be narrower and shifted; the numbers above say how far a standard atmosphere is from a typical day, not how far from the actual day.
5. **The dummy rocket is a weak test of the spread.** Both rockets barely react to atmosphere scatter (apogee sd 0.5 %). A slower, lighter, higher-flying vehicle, a long-range dispersion study, or events such as parachute deployment would stress the atmosphere more. Not a flaw of the tool, a limit of this trial.
6. **Single-station, single-season check.** One station and one fortnight; repeat in winter (strong jet) and at another site before drawing broader conclusions.

## Files
`experiment.py` (flights), `analyze.py` (tables, figures), `check_vs_balloons.py`, `elev_sensitivity.py`, `dummy_light/`, `results/` (`flights_*.csv` one row per flight, `summary.txt`, `summary_light.txt`, `trial_*.png`, `atmosphere_*.npz`).
Re-run: `cd flight_sim_trial/src ; .venv/Scripts/python -W ignore -I ../experiment.py --n 200 --tag afternoon` then `../analyze.py afternoon`.
