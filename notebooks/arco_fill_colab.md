# Boundary-layer fill from ARCO-ERA5 in a Colab notebook

Why: the 8 pressure levels 975-750 hPa are not in the Earthmover store; the Copernicus CDS queue delivers about 1.6 months an hour. ARCO-ERA5 (Google Cloud) has the
same data, but one global hour per chunk, so it only makes sense to read it from inside Google's network. A free Colab notebook does that and keeps only the box
(about 25 MB per month); nothing large comes to your computer.

Checked on one hour of February 1991 against the CDS file: u, v, T agree to 0.001 (float rounding), geopotential to 0.07 m2/s2. Relative humidity is derived from
specific humidity (ARCO has no RH) and agrees to under 1 % RH above 825 hPa (mean abs 0.3-1.0); at 975-900 hPa it differs by 2-8 % RH, but those levels are
below the ground over most of the box (surface pressure ~850-900 hPa), where ERA5 values are extrapolations and `to_heights` does not use them.

Order of work: the CDS download goes forward from 1991. Run the notebook from the END (2025 backwards) so the two meet; whatever month already exists locally is skipped
when the files are copied into `data/raw/era5_cds/`.

## Cells (new notebook, runtime: CPU, High-RAM if offered)

```python
# 1. install and mount Drive (output survives a disconnected session)
!pip -q install gcsfs zarr xarray netCDF4
from google.colab import drive; drive.mount('/content/drive')
```
```python
# 2. upload tempest/ingest/arco_fill.py from the repo (left sidebar -> Files -> upload), then:
!mkdir -p /content/drive/MyDrive/tempest_fill
months = [f"{y}{m:02d}" for y in range(2025, 1990, -1) for m in range(12, 0, -1)]   # newest first
months = [m for m in months if "199101" <= m <= "202512"]
```
```python
# 3. run in slices; each finished month is saved at once, so a dead session loses at most one month. Re-run the cell to resume.
import subprocess, sys
for i in range(0, len(months), 6):
    subprocess.run([sys.executable, "arco_fill.py", "--months", *months[i:i+6], "--out", "/content/drive/MyDrive/tempest_fill", "--workers", "32"], check=False)
```
(`arco_fill.py` is run as a script; if you prefer `python -m`, put the file in a `tempest/ingest/` folder with empty `__init__.py` files.)

Time: one month is 744 hours x about 0.5 GB read inside Google. Colab's bandwidth decides the speed (unknown, probably 100-300 MB/s): expect roughly 20-60 minutes per
month, so 12-hour sessions cover 12-30 months. Free Colab sessions are time-limited; the slices above are resumable.

## On your computer
Copy the finished `<yyyymm>.nc` files into `data/raw/era5_cds/` (next to the CDS `.grib` files; a `.grib` wins if both exist). `python -m tempest.profiles.to_heights`
reads both. The downloader (`fetch_cds`) keeps running for the months Colab did not reach; stop it with the process ID in `data/raw/era5_cds/` logs once all 420 months exist.
