# Data sources and attribution

Tempest-ARKNET's models are trained, corrected and checked with the public data sets below. If you publish results made with the tool, credit the sources the result depends on. The licence terms are the providers' own: follow the linked pages (this file summarises, it does not replace them). Nothing here is redistributed in this repository except the trained model assets in `tempest_weather/assets*`, which are derived from ERA5 and IGRA.

| Source | Used for | Provider and where the terms are |
|---|---|---|
| **ERA5** hourly reanalysis (pressure levels and surface), via the Copernicus Climate Data Store, Google's ARCO-ERA5 store and Earthmover | training profiles of the generator, past mode (`TEMPEST_ERA5_STORE`), the scoring truth | Copernicus Climate Change Service (C3S) / ECMWF; Hersbach et al. (2020), Q. J. R. Meteorol. Soc. 146, 1999-2049. Terms: the Copernicus licence on the Climate Data Store dataset pages |
| **IGRA 2** radiosondes (derived parameters and data) | balloon correction of the training truth, balloon scoring (EPZ 72364, MAF 72265 and others) | NOAA NCEI, Integrated Global Radiosonde Archive version 2; Durre et al. (2018). U.S. government data |
| **ASOS / METAR** airport reports via the Iowa Environmental Mesonet | gust law, ground-wind checks (TCS, MAF), `observe_latest` / `observe_metar` | NWS / FAA observations, archive by the Iowa Environmental Mesonet (Iowa State University) |
| **USCRN** subhourly data (Las Cruces 20 N, Monahans 6 ENE) | independent (non-airport) ground-wind truth | NOAA NCEI, U.S. Climate Reference Network; Diamond et al. (2013). U.S. government data |
| **NREL WIND Toolkit** (WTK) | pad-versus-airport factors, pad Weibull table | National Renewable Energy Laboratory; Draxl et al. (2015). Terms on the NREL data pages |
| **WeatherBench 2** (IFS HRES, IFS ENS, extended range) | forecast mode training and tests | Google Research / ECMWF forecasts; Rasp et al. (2024). ECMWF data under the terms stated by WeatherBench 2 |
| **Open-Meteo** forecast, ensemble and archive APIs | forecast mode at query time, HRRR archive values | open-meteo.com (data from national weather services); see open-meteo.com for the licence and the attribution it asks for |
| **HRRR** (via Open-Meteo / NOAA) | `observe_hrrr` near-ground wind anchor | NOAA NCEP. U.S. government data |
| **Climate indices** (ONI, QBO, WWV, global temperature) | generator inputs | NOAA CPC / PSL and the providers named in `tempest/ingest/fetch_indices.py` |
| **ERA5 invariant fields** (orography, land-sea mask, sub-grid orography) | terrain inputs of the generator | C3S / ECMWF via ARCO-ERA5 (`tempest/ingest/fetch_statics.py`), same terms as ERA5 |
| **Site elevation services**: USGS 3DEP Elevation Point Query, OpenTopoData (NED 10 m), Open-Meteo Elevation (Copernicus GLO-90) | the launch-site elevation (`tempest_weather_v2/elevation.py`) | U.S. Geological Survey (U.S. government data); OpenTopoData; Open-Meteo (Copernicus DEM GLO-90, its own licence; non-commercial use of the free API) |

Software: the tool runs on NumPy (and optionally SciPy, PyTorch, xarray, zarr for training and analysis); RocketPy and OpenRocket formats are written by `Atmosphere.rocketpy_inputs()` / `to_openrocket_csv()` and are not bundled.
