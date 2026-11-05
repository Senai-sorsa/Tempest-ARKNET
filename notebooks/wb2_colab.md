# Lead-time forecast history (IFS HRES, WeatherBench2) in a Colab notebook

Purpose (improvement loop IL-6): calibrate forecast modes F / F2 on real forecasts at 1, 3, 5 and 7 days ahead for 2016-2022, instead of waiting a year for the logger.
The archive keeps one whole-globe forecast per chunk, so extract it inside Google's network; only the pilot box leaves (a few MB per year).
Selection: 00 UTC starts every 4th day (about 320 starts for 2016-2022), leads 24 / 72 / 120 / 168 h, u v T q z on 13 levels plus 10 m wind, 2 m T and surface pressure.
The tool checked the selection on one forecast (a 13 x 13 x 29 box cut out correctly).

```python
!pip -q install gcsfs zarr xarray netCDF4
from google.colab import drive; drive.mount('/content/drive')
# upload tempest/ingest/wb2_fetch.py to the Colab files, then:
!mkdir -p /content/drive/MyDrive/tempest_wb2
!python wb2_fetch.py --out /content/drive/MyDrive/tempest_wb2 --first 2016 --last 2022 --every-days 4 --workers 32
```
Each year is saved when finished, so re-running the cell resumes. Expect 20-90 minutes per year (about 30 GB read per year inside Google).
Then copy `<year>.nc` into `data/raw/wb2_hres/` on your computer and tell Claude; it calibrates the modes (fit 2016-2020, check 2021-22) and logs the result as IL-6.
