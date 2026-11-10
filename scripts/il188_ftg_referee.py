"""IL-188 (2026-11-10): a Denver referee without balloons (IGRA 72469 ends 2022-07): the Denver radar FTG (NEXRAD VAD winds, Level III NVW, cached by scripts/prefetch_nvw_ftg.py) for 2024-25.
For each volume near 23 UTC (about 16 h solar) and 11 UTC (about 04 h solar): the tool's climate-mode atmospheres at the radar (39.787 N, 104.546 W, ground 1675 m) from the Denver DAY set
(assets_denver, 23 UTC only) and the Denver ALL-HOURS set (assets_denver_allhours, both hours), scored with the CRPS of u and v at 500 / 1000 / 1500 / 2000 / 3000 m above the radar,
next to an ERA5 climatology (199 profiles of the same month and UTC hour, 1991-2020, nearest grid point of the Denver day + night stores). The radar has about 3 m/s error (P3), the same for
every ensemble, so skills are conservative but comparable. Answers: is the all-hours Denver model worse than the day model by day on real winds (IL-179), and is the night set skilful?
    PYTHONPATH=. python -W ignore scripts/il188_ftg_referee.py [--out docs/results/logs/il188_ftg_referee.log]"""
import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from p3_vad_vs_balloon import OUT, parse   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.sources import era5_local   # noqa: E402

LAT, LON, ELEV = 39.787, -104.546, 1675.0
LEVELS = (500.0, 1000.0, 1500.0, 2000.0, 3000.0)
STORES = "data/pilot/profiles_denver_full.zarr" + os.pathsep + "data/pilot/profiles_denver_full_night.zarr"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/logs/il188_ftg_referee.log")
    a = ap.parse_args()
    H = list(_core.HEIGHTS)
    j = [H.index(h) for h in LEVELS]
    here = os.path.dirname(api.__file__)
    sets = {"day": os.path.join(here, "assets_denver"), "allhours": os.path.join(here, "assets_denver_allhours")}
    ds = era5_local.open_store(STORES)
    p = int(np.argmin((ds.lat.values - LAT) ** 2 + (ds.lon.values - LON) ** 2))
    tt = pd.DatetimeIndex(ds.time.values)
    clim_ok = (tt.year >= 1991) & (tt.year <= 2020)
    U = ds["u"].isel(point=p).values[:, j]
    V = ds["v"].isel(point=p).values[:, j]
    rng = np.random.default_rng(0)
    rows = []
    for f in sorted(x for x in os.listdir(OUT) if x.startswith("FTG_NVW_202")):
        y, mo, d, hh, mi = (int(x) for x in f.split("_")[2:7])
        t = pd.Timestamp(datetime(y, mo, d, hh, mi)).round("h")
        r = parse(os.path.join(OUT, f), ELEV)
        if r is None:
            continue
        ur, vr = r[0][j], r[1][j]
        if not (np.isfinite(ur).sum() >= 3):
            continue
        sel = np.flatnonzero(clim_ok & (tt.month == t.month) & (tt.hour == t.hour) & np.isfinite(U).all(1))
        if len(sel) < 50:
            continue
        pick = rng.choice(sel, 199, replace=len(sel) < 199)
        ens = {"clim": (U[pick], V[pick])}
        for name, path in sets.items():
            try:
                atm, info = api.atmosphere_set(LAT, LON, t.isoformat() + "+00:00", n=199, seed=int(t.value // 3_600_000_000_000) % 100000, mode="ai", elevation=ELEV, assets=path)
                ens[name] = (np.asarray(atm["u"])[:, j], np.asarray(atm["v"])[:, j])
            except ValueError:
                pass
        ok = np.isfinite(ur) & np.isfinite(vr)
        rec = dict(hour=t.hour)
        for name, (eu, ev) in ens.items():
            c = np.concatenate([crps_ensemble(eu[None, :, ok], ur[None, ok])[0], crps_ensemble(ev[None, :, ok], vr[None, ok])[0]])
            rec[name] = float(c.mean())
        rows.append(rec)
    df = pd.DataFrame(rows)
    lines = [f"IL-188 Denver radar FTG referee 2024-25 ({len(df)} volumes), mean CRPS of u, v at {', '.join(f'{h:.0f}' for h in LEVELS)} m above the radar (m/s), skill vs the ERA5 climatology of the same month and UTC hour"]
    for hh, g in df.groupby("hour"):
        txt = [f"UTC {hh:02d} (about {(hh + LON / 15) % 24:.0f} h solar), n {len(g)}: clim {g['clim'].mean():.3f}"]
        for name in ("day", "allhours"):
            if name in g and g[name].notna().sum() >= 20:
                gg = g.dropna(subset=[name])
                txt.append(f"{name} {gg[name].mean():.3f} (skill {1 - gg[name].mean() / gg['clim'].mean():+.3f}, n {len(gg)})")
        if {"day", "allhours"} <= set(g) and g[["day", "allhours"]].notna().all(1).sum() >= 20:
            gg = g.dropna(subset=["day", "allhours"])
            dd = gg["allhours"] - gg["day"]
            txt.append(f"paired all-hours - day {dd.mean():+.3f} m/s (+-{dd.std() / np.sqrt(len(dd)):.3f})")
        lines.append("  " + " | ".join(txt))
    print("\n".join(lines), flush=True)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
