"""Koppen main climate group per global store point (GLOBAL_PLAN G4: leave-one-climate-out, Koppen-group sampling).

    python -m tempest.geo.koppen fit --out models/global/koppen.npz [--first-year 1991 --last-year 2023]
    from tempest.geo import koppen
    g = koppen.lookup(dict(np.load("models/global/koppen.npz")), lat, lon)    # 0 A tropical, 1 B dry, 2 C temperate, 3 D cold, 4 E polar

Rules (Peel et al. 2007, main groups only): E if the warmest month < 10 C; B if annual precipitation < 10 x Pth with
Pth = 2 MAT (+28 if >= 70 % of it falls in summer, +0 if >= 70 % in winter, else +14); A if the coldest month >= 18 C;
C if the coldest month > 0 C; D otherwise. Summer = Apr-Sep north of the equator, Oct-Mar south of it.
Inputs: monthly mean t2m (data/raw/era5_global) and tp (data/raw/era5_global_extra), training years only.
shortcut: the stores hold one hour per day, so monthly precipitation = mean hourly tp x 24 x days (unbiased over the
cycling hours, noisy for single months; fine for a 33-year class). Upgrade to the ERA5 monthly means if a class flips.
"""
import argparse
import os

import numpy as np

GROUPS = ["A", "B", "C", "D", "E"]
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def classify(t_mon, p_mon, lat):
    """t_mon (P, 12) monthly mean 2 m temperature (C), p_mon (P, 12) monthly precipitation (mm), lat (P,) -> (P,) group 0..4."""
    t_mon, p_mon, lat = np.asarray(t_mon, float), np.asarray(p_mon, float), np.asarray(lat, float)
    tw, tc, mat, map_ = t_mon.max(1), t_mon.min(1), t_mon.mean(1), p_mon.sum(1)
    north = np.zeros(12, bool)
    north[3:9] = True                                                    # Apr-Sep
    summer = np.where(lat[:, None] >= 0, north[None], ~north[None])
    ps = (p_mon * summer).sum(1) / np.maximum(map_, 1e-9)
    pth = 2 * mat + np.where(ps >= 0.7, 28, np.where(ps <= 0.3, 0, 14))
    g = np.where(tc >= 18, 0, np.where(tc > 0, 2, 3))
    g = np.where(map_ < 10 * pth, 1, g)
    return np.where(tw < 10, 4, g).astype(np.int8)


def monthly(first=1991, last=2023, store=None, extra=None):
    """Per store point and calendar month: mean t2m (C) and precipitation (mm/month) over [first, last]."""
    from tempest.geo import global_store as gs
    if last > 2023:
        raise ValueError("the Koppen classes use training years only (<= 2023)")
    store, extra = store or gs.STORE, extra or gs.EXTRA
    pts = gs.points(store)
    P = len(pts["lat"])
    st, sp, n = np.zeros((P, 12)), np.zeros((P, 12)), np.zeros(12)
    for name in gs.months(first, last, store):
        mo = int(name[5:7]) - 1
        if not os.path.exists(os.path.join(extra, f"{name}.npz")):
            continue                                                      # both fields from the same months only
        st[:, mo] += np.nanmean(gs.month(name, store)["t2m"], 0) - 273.15
        sp[:, mo] += np.nanmean(gs.extra(name, extra)["tp"], 0) * 24 * 1000 * DAYS[mo]
        n[mo] += 1
    if (n == 0).any():
        raise ValueError(f"no data for calendar months {np.flatnonzero(n == 0) + 1}")
    return pts, st / n, sp / n


def fit(first=1991, last=2023, store=None, extra=None):
    pts, t, p = monthly(first, last, store, extra)
    return dict(lat=pts["lat"], lon=pts["lon"], group=classify(t, p, pts["lat"]), t_mon=t.astype(np.float32),
                p_mon=p.astype(np.float32), first=first, last=last)


def lookup(tab, lat, lon):
    """Nearest table point (great circle) -> Koppen group 0..4."""
    from tempest.geo.tropo_clim import _nearest
    return np.asarray(tab["group"])[_nearest(tab, lat, lon)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--first-year", type=int, default=1991)
    f.add_argument("--last-year", type=int, default=2023)
    a = ap.parse_args()
    t = fit(a.first_year, a.last_year)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "wb") as fh:
        np.savez(fh, **t)
    print(f"wrote {a.out}: " + ", ".join(f"{g} {np.mean(t['group'] == i):.0%}" for i, g in enumerate(GROUPS)))


if __name__ == "__main__":
    main()
