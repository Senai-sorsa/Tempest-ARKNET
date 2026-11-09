"""V2: low-level wind profile shape (10 -> 200 m), the only layer that moves apogee. Median ratio of wind speed at 50 / 80 / 100 / 200 m to the 10 m speed, by 10 m speed class, daytime (local 10-17 h), at TCS and MAF, from
 (a) the ERA5 profile store (2024-25, nearest grid point), (b) HRRR (Open-Meteo archive, 10 m and 80 m wind, 2024-25), (c) the tool in climate mode (15th of each month, 12:00 and 15:00 local, n = 300), (d) the tool in past mode (ERA5 + balloon correction)
 for 100 random daytime hours of 2024-25, (e) IGRA soundings at EPZ / MAF (00Z = 17-18 local in summer, interpolated to the model heights) for the balloon view.

    PYTHONPATH=. TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore scripts/v2_profile_shape.py
"""
import os
import sys
import warnings
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch, _net   # noqa: E402

ST = {"TCS": (33.2369, -107.2672, 1479.0, "America/Denver", "USM00072364"), "MAF": (31.9425, -102.2019, 872.0, "America/Chicago", "USM00072265")}
CLASSES = [(0, 3), (3, 6), (6, 10), (10, 30)]
ZS = [50.0, 80.0, 100.0, 200.0]


def interp_speed(h, speed, z):
    """speed (N, H) at heights h -> (N,) at height z by linear interpolation in log height."""
    lh = np.log(h)
    out = np.empty(len(speed))
    for i in range(len(speed)):
        out[i] = np.interp(np.log(z), lh, speed[i])
    return out


def table(name, s10, prof_fn):
    """prof_fn(z) -> speed at z for every sample. Prints median ratio by class."""
    row = []
    for lo, hi in CLASSES:
        sel = (s10 >= lo) & (s10 < hi) & (s10 > 0.3)
        if sel.sum() < 15:
            row.append("   -   " * len(ZS))
            continue
        row.append(" ".join(f"{np.median(prof_fn(z)[sel] / s10[sel]):5.2f}" for z in ZS) + f" (n{sel.sum()})")
    print(f"  {name:34} " + " | ".join(row))


def hrrr(lat, lon, year):
    url = (f"https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&start_date={year}-01-01&end_date={year}-12-31"
           f"&hourly=wind_speed_10m,wind_speed_80m&models=ncep_hrrr_conus&wind_speed_unit=ms&timezone=UTC")
    h = _net.fetch_json(url, service="open-meteo", retries=2, timeout=90)["hourly"]
    return [datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc) for t in h["time"]], np.array([np.nan if v is None else v for v in h["wind_speed_10m"]]), np.array([np.nan if v is None else v for v in h["wind_speed_80m"]])


def main():
    warnings.filterwarnings("ignore")
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(REPO, "data", "pilot", "profiles.zarr")
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    ht = z["height"].values.astype(float)
    low = ht <= 300
    tt = z["time"].values
    yr = tt.astype("datetime64[Y]").astype(int) + 1970
    print("columns per class (speed at 10 m): " + " | ".join(f"{lo}-{hi} m/s" for lo, hi in CLASSES) + "; entries are median ratio of speed at " + "/".join(f"{int(q)}" for q in ZS) + " m to the 10 m speed")
    rng = np.random.default_rng(0)
    for name, (lat, lon, el, tz, sid) in ST.items():
        zi = ZoneInfo(tz)
        print(f"\n{name} (daytime, local 10-17 h)")
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        sel_t = np.flatnonzero((yr >= 2024) & (yr <= 2025))
        lh = np.array([datetime.fromtimestamp(tt[k].astype("datetime64[s]").astype(int), tz=timezone.utc).astimezone(zi).hour for k in sel_t])
        day = sel_t[(lh >= 10) & (lh <= 17)]
        u = z["u"].isel(point=i, time=day).values[:, low].astype(float)
        v = z["v"].isel(point=i, time=day).values[:, low].astype(float)
        sp = np.hypot(u, v)
        table("ERA5 store", sp[:, 0], lambda zz: interp_speed(ht[low], sp, zz))
        for y in (2024, 2025):
            pass
        tl, s10, s80 = [], [], []
        for y in (2024, 2025):
            a, b, c = hrrr(lat, lon, y)
            tl += a
            s10 += list(b)
            s80 += list(c)
        s10, s80 = np.array(s10), np.array(s80)
        lhr = np.array([t.astimezone(zi).hour for t in tl])
        m = (lhr >= 10) & (lhr <= 17) & np.isfinite(s10) & np.isfinite(s80)
        for lo, hi in CLASSES:
            sel = m & (s10 >= lo) & (s10 < hi) & (s10 > 0.3)
            print(f"  HRRR 80 m / 10 m, class {lo}-{hi} m/s: median {np.median(s80[sel] / s10[sel]):5.2f} (n{sel.sum()})" if sel.sum() > 15 else f"  HRRR class {lo}-{hi}: too few")
        # tool climate
        s10c, prof = [], []
        for mth in range(1, 13):
            for hh in (12, 15):
                s = Launch(lat, lon, f"2025-{mth:02d}-15 {hh:02d}:00", mode="ai", n=300, units="si", elevation=el, tz=tz, seed=4)._ensure_pool()["samples"]
                h_ = np.asarray(s["height_agl"], float)
                sp_ = np.hypot(s["u"], s["v"])
                low_ = h_ <= 300
                s10c.append(sp_[:, 0])
                prof.append(np.stack([np.interp(np.log(zz), np.log(h_[low_]), 0 * h_[low_]) * 0 + 0 for zz in ZS], 0).T if False else np.stack([interp_speed(h_[low_], sp_[:, low_], zz) for zz in ZS], 1))
        s10c, prof = np.concatenate(s10c), np.concatenate(prof)
        table("tool climate mode", s10c, lambda zz: prof[:, ZS.index(zz)])
        # tool past
        picks = rng.choice(day, 60, replace=False)
        s10p, profp = [], []
        for k in picks:
            t = tt[k].astype("datetime64[s]").astype(int)
            dt = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(zi)
            try:
                s = Launch(lat, lon, dt.strftime("%Y-%m-%d %H:%M"), mode="past", n=40, units="si", elevation=el, tz=tz, seed=4)._ensure_pool()["samples"]
            except Exception:   # noqa: BLE001
                continue
            h_ = np.asarray(s["height_agl"], float)
            sp_ = np.hypot(s["u"], s["v"])
            low_ = h_ <= 300
            s10p.append(sp_[:, 0])
            profp.append(np.stack([interp_speed(h_[low_], sp_[:, low_], zz) for zz in ZS], 1))
        if s10p:
            s10p, profp = np.concatenate(s10p), np.concatenate(profp)
            table("tool past mode", s10p, lambda zz: profp[:, ZS.index(zz)])
        # balloons
        d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
        yrs = d["time"].astype("datetime64[Y]").astype(int) + 1970
        ok = (yrs >= 2015)
        hh_ = d["heights"]
        idx = np.flatnonzero(hh_ <= 300)
        ub, vb = d["u"][ok][:, idx].astype(float), d["v"][ok][:, idx].astype(float)
        bad = (d["u"][ok][:, idx] == -32768) | (d["v"][ok][:, idx] == -32768)
        ub[bad] = np.nan
        vb[bad] = np.nan
        spb = np.hypot(ub, vb) * 0.1
        good = np.isfinite(spb).all(1)
        spb = spb[good]
        table("IGRA balloons (00Z+12Z, 2015-25)", spb[:, 0], lambda zz: interp_speed(hh_[idx], spb, zz))


if __name__ == "__main__":
    main()
