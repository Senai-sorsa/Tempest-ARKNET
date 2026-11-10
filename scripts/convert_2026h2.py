"""Final-test window 2026 July-October: turn the CDS GRIB files of scripts/fetch_final_window.py into the two inputs tempest.profiles.to_heights reads, in exactly the layout of the
training stores, so the test months go through the same profile and dataset recipe:
  data/raw/era5_em_2026h2/<var>.zarr   the 13 Earthmover levels (u, v, t, r, z; dims valid_time, pressure_level, latitude, longitude 0-360) and the surface fields (u10, v10, u100,
                                       v100, t2m, d2m, sp), with the static lsm / z_sfc copied from data/raw/era5_em80;
  data/raw/era5_cds_2026h2/<yyyymm>.nc the 8 boundary-layer levels 975-750 hPa (the fill to_heights adds; same names and dims as tempest.ingest.arco_fill writes).
Only reads 2026 July-October files and writes into two NEW folders; nothing is scored here.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/convert_2026h2.py [--months 202607 202608 202609 202610]
"""
import argparse
import os

import cfgrib
import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "data", "raw", "era5_2026h2")
RAW = os.path.join(REPO, "data", "raw", "era5_em_2026h2")
FILL = os.path.join(REPO, "data", "raw", "era5_cds_2026h2")
EM_LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]
BL_LEVELS = [975, 950, 900, 875, 825, 800, 775, 750]
SFC = ["u10", "v10", "u100", "v100", "t2m", "d2m", "sp"]


def open_grib(path):
    return xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})


def surface(path):
    parts = cfgrib.open_datasets(path, backend_kwargs={"indexpath": ""})
    out = {}
    for p in parts:
        for v in p.data_vars:
            if v in SFC:
                out[v] = p[v].drop_vars([c for c in p[v].coords if c not in ("time", "latitude", "longitude")], errors="ignore")
    missing = [v for v in SFC if v not in out]
    if missing:
        raise SystemExit(f"{path}: surface fields missing {missing} (found {sorted(out)})")
    return xr.Dataset(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*", default=["202607", "202608", "202609", "202610"])
    ap.add_argument("--raw-out", default=RAW, help="output folder of the Earthmover-style stores (a scratch folder for a test run)")
    ap.add_argument("--fill-out", default=FILL)
    a = ap.parse_args()
    raw_out, fill_out = a.raw_out, a.fill_out
    for m in a.months:
        for k in ("pl1", "pl2", "pl3", "sfc"):
            if not os.path.exists(os.path.join(SRC, f"{k}_{m}.grib")):
                raise SystemExit(f"missing {k}_{m}.grib: wait for scripts/fetch_final_window.py")
    os.makedirs(raw_out, exist_ok=True)
    os.makedirs(fill_out, exist_ok=True)
    static = xr.open_zarr(os.path.join(REPO, "data", "raw", "era5_em80", "u10.zarr"))[["lsm", "z_sfc"]].load()
    pls, sfcs = [], []
    for m in a.months:
        pl = xr.concat([open_grib(os.path.join(SRC, f"{k}_{m}.grib"))[["u", "v", "t", "r", "z"]] for k in ("pl1", "pl2", "pl3")], dim="isobaricInhPa").sortby("isobaricInhPa", ascending=False).load()
        assert sorted(pl.isobaricInhPa.values.astype(int).tolist()) == sorted(EM_LEVELS + BL_LEVELS), pl.isobaricInhPa.values
        fill = pl.sel(isobaricInhPa=BL_LEVELS).drop_vars([c for c in pl.coords if c not in ("time", "isobaricInhPa", "latitude", "longitude")], errors="ignore")
        fill.to_netcdf(os.path.join(fill_out, f"{m}.nc"))
        pls.append(pl.sel(isobaricInhPa=EM_LEVELS))
        sfcs.append(surface(os.path.join(SRC, f"sfc_{m}.grib")).load())
        print(f"{m}: {pl.sizes['time']} hours, fill written", flush=True)
    pl = xr.concat(pls, dim="time")
    sf = xr.concat(sfcs, dim="time")

    def em_style(da):
        da = da.drop_vars([c for c in da.coords if c not in ("time", "isobaricInhPa", "latitude", "longitude")], errors="ignore")   # cfgrib's own valid_time / step / number first
        da = da.rename({"time": "valid_time"})
        if "isobaricInhPa" in da.dims:
            da = da.rename({"isobaricInhPa": "pressure_level"}).assign_coords(pressure_level=np.asarray(EM_LEVELS, float))
        da = da.drop_vars([c for c in da.coords if c not in ("valid_time", "pressure_level", "latitude", "longitude")], errors="ignore")
        da = da.assign_coords(longitude=(da.longitude % 360)).sortby("latitude", ascending=False).sortby("longitude")
        return da.astype(np.float32)
    for v in ["u", "v", "t", "r", "z"]:
        ds = em_style(pl[v]).to_dataset(name=v).assign_coords(lsm=static.lsm, z_sfc=static.z_sfc)
        ds.chunk({"valid_time": -1}).to_zarr(os.path.join(raw_out, f"{v}.zarr"), mode="w")
    for v in SFC:
        ds = em_style(sf[v]).to_dataset(name=v).assign_coords(lsm=static.lsm, z_sfc=static.z_sfc)
        ds.chunk({"valid_time": -1}).to_zarr(os.path.join(raw_out, f"{v}.zarr"), mode="w")
    t = pl.time.values
    print(f"written {raw_out} ({len(t)} hours, {str(t[0])[:13]} .. {str(t[-1])[:13]}) and {fill_out}")


if __name__ == "__main__":
    main()
