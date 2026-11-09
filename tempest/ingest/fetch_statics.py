"""ERA5 invariant fields (global, 0.25 deg) from ARCO-ERA5: one 721 x 1440 field each, < 100 MB in all.

    python -m tempest.ingest.fetch_statics [--out data/raw/era5_static/era5_invariants.npz]

z_sfc = surface geopotential (m2/s2; / 9.80665 = orography height), lsm = land-sea mask, sdor = standard deviation of
sub-grid orography, slor / anor / isor = slope, angle and anisotropy of sub-grid orography. Latitude runs 90 -> -90 and
longitude 0 -> 359.75, the same grid as tempest.ingest.fetch_global.to_grid, so field[ilat, ilon] is a point's value.
These are the place-describing inputs loop 3 asked for (coordinates cannot tell the model where it is; terrain can).
"""
import argparse
import os

import numpy as np

import urllib.request

from numcodecs import Blosc

from tempest.ingest.arco_fill import URL

BASE = "https://storage.googleapis.com/gcp-public-data-arco-era5/" + URL + "/"

VARS = {"geopotential_at_surface": "z_sfc", "land_sea_mask": "lsm", "standard_deviation_of_orography": "sdor",
        "slope_of_sub_gridscale_orography": "slor", "angle_of_sub_gridscale_orography": "anor",
        "anisotropy_of_sub_gridscale_orography": "isor"}


def chunk(key, dtype="<f4"):
    """One raw zarr-v2 chunk of the ARCO store (blosc-compressed) as a flat array; plain urllib, no fsspec/aiohttp needed."""
    with urllib.request.urlopen(urllib.request.Request(BASE + key, headers={"User-Agent": "tempest-arknet"}), timeout=300) as r:
        return np.frombuffer(Blosc().decode(r.read()), dtype)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/era5_static/era5_invariants.npz")
    a = ap.parse_args()
    if os.path.exists(a.out):
        print(f"{a.out}: exists, skipping"); return
    lat, lon = chunk("latitude/0"), chunk("longitude/0")
    assert lat.size == 721 and lat[0] == 90 and lat[-1] == -90 and lon.size == 1440 and lon[0] == 0, "unexpected ARCO grid"
    t = int((np.datetime64("2020-01-01T00") - np.datetime64("1900-01-01T00")) // np.timedelta64(1, "h"))  # time chunk = hours since 1900; invariants are the same at every step
    out = {}
    for name, short in VARS.items():
        out[short] = chunk(f"{name}/{t}.0.0").reshape(721, 1440).astype(np.float32)
        print(f"{short}: {out[short].shape} min {np.nanmin(out[short]):.3g} max {np.nanmax(out[short]):.3g}", flush=True)
    h = out["z_sfc"] / 9.80665
    assert 4500 < h.max() < 9000 and 0 <= out["lsm"].min() and out["lsm"].max() <= 1, "orography / mask out of range"
    i, j = int(round((90 - 39.75) / 0.25)), int(round((360 - 105.0) / 0.25))  # Denver foothills: land, ~1.5-3 km
    assert out["lsm"][i, j] > 0.9 and 1200 < h[i, j] < 3500, (out["lsm"][i, j], h[i, j])
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out + ".part", "wb") as f:
        np.savez_compressed(f, lat=lat, lon=lon, **out)
    os.replace(a.out + ".part", a.out)
    print(f"{a.out}: {os.path.getsize(a.out) / 1e6:.1f} MB, Denver check h={h[i, j]:.0f} m ok")


if __name__ == "__main__":
    main()
