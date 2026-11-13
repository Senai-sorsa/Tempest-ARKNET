"""AU-6 step 0 (New_Plan 15.2): do the balloon soundings that `sonde.py` drops as incomplete depend on the weather?

    python scripts/au6_dropped.py [--first-year 2024] [--last-year 2025] [--out docs/results/logs/au6_dropped.txt]

Per station and launch hour (00Z, 12Z): share of soundings in the test years that miss any of u, v, T, RH at the 44
heights or the surface (the `sonde.py` rule); that share by tercile of ERA5 500 hPa wind speed at the launch hour
(nearest grid point, the height closest to 5.6 km above sea level, about 500 hPa here) and by month; and which
variable / lowest missing height caused the drop. Pass rule: close if the windy-minus-calm share is <= 5 points.
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate.station import STATIONS, era5_at, nearest_point, read_igra
from tempest.profiles.to_heights import HEIGHTS, PROFILE

Z500 = 5600.0  # m above sea level, about 500 hPa in the subtropics


def causes(prof, sfc):
    """(S, 4, 44), (S, 3) -> per sounding the cause label of the drop ('' = complete)."""
    out = []
    for p, s in zip(prof, sfc):
        bad = [f"{v}<{HEIGHTS[np.flatnonzero(~np.isfinite(p[i]))[0]] / 1000:.0f}km"
               for i, v in enumerate(("u", "v", "T", "RH")) if not np.isfinite(p[i]).all()]
        if not np.isfinite(s).all():
            bad.append("surface")
        out.append("+".join(bad))
    return np.array(out)


def coarse(c):
    """Cause label -> 'complete', 'RH>10km only', 'wind', 'T', 'RH<=10km', 'surface'."""
    if c == "":
        return "complete"
    parts = c.split("+")
    if all(p.startswith("RH<") and int(p[3:-2]) > 10 for p in parts):
        return "RH>10km only"
    for key, name in (("u<", "wind"), ("v<", "wind"), ("T<", "T"), ("RH<", "RH<=10km"), ("surface", "surface")):
        if any(p.startswith(key) for p in parts):
            return name
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="data/pilot/profiles.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--out", default="docs/results/logs/au6_dropped.txt")
    a = ap.parse_args()
    ds = xr.open_zarr(a.profiles)
    rows = []
    for sid, (slat, slon) in STATIONS.items():
        t, prof, sfc = read_igra(f"{a.igra}/{sid}-drvd.txt.zip", a.first_year, a.last_year)
        p = nearest_point(ds, slat, slon)
        k = int(np.argmin(np.abs(HEIGHTS + float(ds.z_sfc.values[p]) - Z500)))
        e = era5_at(ds, p, t)
        ws = np.hypot(e[:, PROFILE.index("u"), k], e[:, PROFILE.index("v"), k])
        c = causes(prof, sfc)
        rows.append(pd.DataFrame(dict(sid=sid, year=t.year, month=t.month, hour=t.hour, ws500=ws, cause=c,
                                      kind=[coarse(x) for x in c], dropped=c != "")))
    d = pd.concat(rows, ignore_index=True)
    d = d[np.isfinite(d.ws500)]
    # terciles per station and hour, so a windier site does not fill the windy class alone
    d["tercile"] = d.groupby(["sid", "hour"]).ws500.transform(lambda s: pd.qcut(s, 3, labels=False))
    lines = [f"AU-6 step 0: soundings {a.first_year}-{a.last_year} dropped as incomplete (sonde.py rule), "
             f"by ERA5 wind at {Z500 / 1000:.1f} km MSL tercile; n = {len(d)}", ""]
    pct = lambda s: f"{100 * s.mean():5.1f}"
    lines.append("station hour  n     dropped%  calm  mid  windy  windy-calm")
    worst = 0.0
    for (sid, h), g in d.groupby(["sid", "hour"]):
        by = g.groupby("tercile").dropped.mean() * 100
        diff = by.get(2, np.nan) - by.get(0, np.nan)
        worst = max(worst, diff)
        lines.append(f"{sid} {h:02d}Z {len(g):5d}  {pct(g.dropped)}   {by.get(0, np.nan):5.1f} {by.get(1, np.nan):5.1f} "
                     f"{by.get(2, np.nan):5.1f}  {diff:+5.1f}")
    lines += ["", "cause of the drop (share of all soundings, %) by tercile:"]
    lines.append((pd.crosstab(d.kind, d.tercile, normalize="columns") * 100).round(1).to_string())
    lines += ["", "dropped % by month (all stations and hours):"]
    lines.append((d.groupby("month").dropped.mean() * 100).round(1).to_frame().T.to_string())
    lines += ["", "dropped % by year:", (d.groupby(["sid", "year"]).dropped.mean() * 100).round(1).to_string()]
    lines += ["", "most common exact causes:", d[d.dropped].cause.value_counts().head(12).to_string()]
    verdict = "CLOSE (<= 5 points)" if worst <= 5 else "FIX NEEDED (> 5 points)"
    lines += ["", f"largest windy-minus-calm difference: {worst:+.1f} points -> {verdict}"]
    # season confound: windy terciles are mostly winter; terciles inside each station x hour x month
    ym = pd.to_datetime(dict(year=d.year, month=d.month, day=1)).dt.strftime("%Y-%m")
    low = d.cause.str.match(r"u<[02]km")
    lines += ["", "drops from wind missing below 2 km, by station and month (outage check):",
              d[low].groupby(["sid", ym[low]]).size().loc[lambda s: s >= 5].to_string()]
    f = d[~ym.isin(["2024-01", "2024-02", "2024-03"])].copy()
    f["mt"] = f.groupby(["sid", "hour", "month"]).ws500.transform(lambda s: pd.qcut(s, 3, labels=False, duplicates="drop"))
    lines += ["", "dropped % by within-month tercile, 2024-01..03 excluded (season and outage removed):",
              (f.groupby(["sid", "hour", "mt"]).dropped.mean() * 100).round(1).unstack().to_string()]
    text = "\n".join(lines)
    print(text)
    with open(a.out, "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
