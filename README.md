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

## Status

Pilot box 1991–2025 downloaded and converted; training file built (8M rows). Copernicus boundary-layer
fill downloading. The generator (option 3A) is written and tested but not trained yet. Known issues and next fixes: the design review at the end
of [docs/PLAN.md](docs/PLAN.md).

## Run

```
uv sync
python -m pytest                                   # 23 tests, CPU is fine
python -m tempest.ingest.fetch_earthmover          # ERA5 13 levels + surface, ~40 min, no account needed
python -m tempest.ingest.fetch_indices             # ENSO / QBO / WWV indices
python -m tempest.ingest.fetch_igra                # radiosondes (NCEI)
python -m tempest.profiles.to_heights              # → data/pilot/profiles.zarr (~59 GB)
python -m tempest.calibrate.station                # balloon correction → models/station_map.npz (+ held-out check)
python -m tempest.generator.build_dataset --station-map models/station_map.npz   # → data/train/pilot.npz
python -m tempest.generator.train --data data/train/pilot.npz --out models/generator_pilot.pt   # GPU
python -m tempest.scoring.score --model models/generator_pilot.pt --data data/train/pilot.npz    # scorecard + charts in models/generator_pilot_report/
python -m tempest.scoring.sonde --model models/generator_pilot.pt --data data/train/pilot.npz    # vs real weather balloons
```
Optional boundary-layer fill: create a free Copernicus CDS account, put `url:` and `key:` lines in
`%USERPROFILE%\.ecmwfdatastoresrc` (never commit it), then `python -m tempest.ingest.fetch_cds`.

## Docs

[docs/PLAN.md](docs/PLAN.md) (plan), [docs/PHASE1.md](docs/PHASE1.md) (build spec),
[docs/research-notes.md](docs/research-notes.md). Accuracy suggestions under review:
[suggestions-copoilet.md](suggestions-copoilet.md), [GPT-suggestions.md](GPT-suggestions.md).

## License

MIT, see [LICENSE](LICENSE).
