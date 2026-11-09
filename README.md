# Tempest-ARKNET

Weather for Monte Carlo flight simulation. Give it a place in the contiguous US, a date and a time
between 8 am and 8 pm. It returns N vertically coherent atmospheric profiles (wind, temperature and
humidity at 44 fixed heights from 10 m to 18 km above ground) plus the mean and standard deviation of
each, for any date from the past to about three years ahead. Pilot sites: Spaceport America and Midland, TX.

How it works by lead time:
- Next 15 days: pooled members of Google WeatherNext 2 (64) and the ECMWF ensemble (51), from Open-Meteo.
- Further ahead: a neural generator (Engression) trained on radiosonde-corrected ERA5, with real ERA5
  profiles from similar days and hours (shifted by tested trend, ENSO and QBO terms) as baseline and fallback.
- Past dates: ERA5, or the Open-Meteo historical-forecast API.

Spreads are calibrated against radiosondes. Output goes to the `dynamics` Monte Carlo TOML format plus a
samples file.

## Status (2026-11-05)

- **Climate generator (Phase 2 model `p2f`).** Engression network, 4 members, trained 1991-2020 (+ validation 2021-23) on balloon-corrected ERA5 with humidity learned as dewpoint
  depression and a tail-weighted wind-shear loss. On the 2024-25 development years it beats the recent-15-year climatology by 2.8 % (CRPS, ERA5) and 0.8 % (real balloons), and the Earth-GRAM-style
  reference by about 6.7 % / 2.8 %; its 99 % ranges hold about 99 % of outcomes. Month-ahead skill stays close to climatology by nature; the value is honest, coherent profiles.
- **Past dates (mode P).** ERA5 for the exact hour, corrected by a residual network trained against balloons: median error 6 % below raw ERA5, CRPS 5.5 % below the older station correction.
- **Extra outputs.** Pressure, density and speed of sound derived from each sample, vertical wind (w-head), 10 m gusts, 24 h soak history, thermal scaling (physics only), joint 99 % band, coupled sample files.
- **Forecast modes (Phase 4)** are built up to the data limits: the ensemble-to-heights converter, router and clients exist; calibration waits on the daily logger archive (started 2026-11-05).
- **Tool (Phase 5).** Plan in `docs/plans/PHASE5_TOOL.md`.
- Full history, every experiment and its numbers with intervals: [docs/plans/PLAN.md](docs/plans/PLAN.md); Phase 4 log: [docs/logs/PHASE4_LOG.md](docs/logs/PHASE4_LOG.md); work plan: `docs/plans/PHASED_PLAN.md`.
  The 2024-25 years are "development" years (used for many decisions); 2026 January-June is the untouched final test.

## Run

```
uv sync
python -m pytest -q                                # about 90 tests, 4 min on CPU (do not run during scoring)
python -m tempest.ingest.fetch_earthmover          # ERA5 13 levels + surface; add --only fg10 blh ssrd slhf ssr w for the Phase 3 fields
python -m tempest.ingest.fetch_indices             # ENSO / QBO / WWV / global temperature
python -m tempest.ingest.fetch_igra                # radiosondes (NCEI);  fetch_asos: airport gusts (Iowa Mesonet)
python -m tempest.profiles.to_heights              # pressure levels -> 44 heights above ground
python -m tempest.calibrate.station                # balloon correction map
python -m tempest.generator.build_dataset --profiles P.zarr --station-map M.npz --rh-target dpd   # training file
python -m tempest.generator.train --data D.npz --out models/X.pt --max-year 2023 --min-year 1991 --config configs/generator_p2f.toml
python -m tempest.calibrate.spread --model models/X.pt --data D.npz --year 2023 --from-year 2021 --rows 60000 --m 199
python -m tempest.scoring.score --model models/X.pt --data D.npz --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/X.calib2021.npz [--extras --stress --joint J]
python -m tempest.scoring.sonde --model models/X.pt --data D.npz --profiles P.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/X.calib2021.npz
python -m tempest.output.atmosphere --lat 32.99 --lon -106.97 --when "2027-06-16 15:00" --out out/demo     # one call -> coupled atmosphere files
python scripts/compare_headline.py OLD_headline.csv NEW_headline.csv           # the phase pass rule
```
Flight validation: record the pad weather of every launch in [docs/templates/pad_observations.csv](docs/templates/pad_observations.csv) and check the tool against it with `python scripts/atmosphere_check.py FILE.csv` (judges the air directly, without the rocket model's error).
Every new option is a flag that is off by default. Forecast logger: `python -m tempest.ops.logger --loop 12` and `python -m tempest.ops.logger_p4 --loop 24`.
Cap long jobs at 12 of the 20 CPU threads (`source scripts/cap_cpu.sh` first). CDS key: `%USERPROFILE%\.ecmwfdatastoresrc` (never commit it).

## Docs

[ATTRIBUTION.md](ATTRIBUTION.md) (data sources and how to credit them), [examples/monte_carlo_quickstart.py](examples/monte_carlo_quickstart.py) (Monte Carlo workflow), [docs/plans/PLAN.md](docs/plans/PLAN.md) (plan and results), [docs/logs/PHASE4_LOG.md](docs/logs/PHASE4_LOG.md), [docs/plans/TOOL_PLAN.md](docs/plans/TOOL_PLAN.md) (older tool plan),
[docs/research/research-notes.md](docs/research/research-notes.md), [docs/agent/ASK_LATER.md](docs/agent/ASK_LATER.md) (items waiting for the user). **All documents, by kind: [docs/README.md](docs/README.md).**

## License

MIT, see [LICENSE](LICENSE).
