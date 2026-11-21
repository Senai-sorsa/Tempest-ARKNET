"""23.T4 step 0 probe: read the first members of one COSMIC-2 NRT atmPrf daily tarball (streamed) and print file names and variables."""
import io, sys, tarfile, urllib.request
import xarray as xr
u = "https://data.cosmic.ucar.edu/gnss-ro/cosmic2/nrt/level2/2024/160/atmPrf_nrt_2024_160.tar.gz"
tf = tarfile.open(fileobj=urllib.request.urlopen(u, timeout=120), mode="r|gz")
n = 0
for m in tf:
    if not m.isfile():
        continue
    b = tf.extractfile(m).read()
    ds = xr.open_dataset(io.BytesIO(b), engine="scipy" if b[:3] == b"CDF" else "h5netcdf")
    if n == 0:
        print(m.name, len(b), dict(ds.sizes)); print(list(ds.data_vars)); print({k: ds.attrs[k] for k in list(ds.attrs)[:25]})
    print(m.name, float(ds.lat.mean()) if "lat" in ds else "-", float(ds.lon.mean()) if "lon" in ds else "-", ds.attrs.get("lat"), ds.attrs.get("lon"))
    n += 1
    if n >= 4:
        break
