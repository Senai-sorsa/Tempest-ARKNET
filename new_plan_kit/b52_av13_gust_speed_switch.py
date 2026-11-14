"""New_Plan 13 AV13: regional (Denver) gust law switched by speed. IL-183 (scripts/gust_1min_region.py, docs/results/logs/gust_1min_denver.log): the region's ERA5-wind
Gumbel law ties the built-in NM/TX law overall (CRPS 1.10 vs 1.10, station flag 1), better above 5 m/s, worse below. Switch: region law where the MODEL (ERA5 10 m) wind >= 5 m/s,
built-in law below. The 5 m/s threshold is fixed from that log, not tuned here.
Baseline = built-in ERA5-wind law with station flag 1 (the one the region law tied; flag 0 is reported, no rule). Truth = physical gust (highest 5-second peak in the 10 min
up to :53, ASOS one-minute), same joins / filters as IL-183. Both laws draw from the SAME Gumbel uniforms (199 members), so below 5 m/s the switch equals the baseline exactly.
Cross-station (the rule's test): region law fitted on one airport <= 2020, scored on the OTHER airport 2021-23, both directions (DEN -> APA, APA -> DEN), cases pooled.
Gain = 100 (1 - CRPS switch / CRPS built-in), 95 % interval = paired bootstrap of test cases (2000 draws).
Rule written 2026-11-14 before any AV13 run (New_Plan 13 AV13 row, unchanged):
PASS: cross-station gain > 0 with the 95 % interval excluding 0, AND not worse below 5 m/s model wind (gain there >= 0).
KILL: the cross-station test loses the gain (cross-station gain <= 0).
Otherwise MISS: record, no adoption. Shipping a region law is an asset change and needs the user in any case.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b52_av13_gust_speed_switch.py
Result: docs/results/logs/kit_b52_av13_gust_speed_switch.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b52_av13_gust_speed_switch"
STATIONS = (("DEN", 39.8466, -104.6562), ("APA", 39.5701, -104.8493))
ONEMIN = os.path.join(K.REPO, "data", "raw", "asos1min_denver")
ERA5 = os.path.join(K.REPO, "data", "raw", "era5_em_denver_full")
SWITCH = 5.0
M = 199


def judge(g, lo, hi, g_low):
    if g <= 0:
        return f"KILL (cross-station gain {g:+.2f} % <= 0)"
    if lo > 0 and g_low >= 0:
        return f"PASS (cross-station gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}], below {SWITCH:g} m/s {g_low:+.2f} %)"
    return f"MISS (cross-station gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}] (interval must exclude 0), below {SWITCH:g} m/s {g_low:+.2f} % (needs >= 0))"


def gain_ci(c_a, c_b, rng, n=2000):
    """CRPS gain of b over a in % and its paired-bootstrap 95 % interval."""
    g = 100 * (1 - c_b.mean() / c_a.mean())
    gs = np.empty(n)
    for k in range(n):
        i = rng.integers(0, len(c_a), len(c_a))
        gs[k] = 100 * (1 - c_b[i].mean() / c_a[i].mean())
    return g, np.percentile(gs, 2.5), np.percentile(gs, 97.5)


def switch(x_builtin, x_region, w_model):
    return np.where((w_model >= SWITCH)[:, None], x_region, x_builtin)


def load():
    from gust_1min import physical_hourly
    from gust_1min_region import era5_wind
    rows = []
    for sid, lat, lon in STATIONS:
        h = pd.concat([physical_hourly(f) for f in sorted(glob.glob(os.path.join(ONEMIN, f"{sid}_*.csv")))])
        h = h[~h.index.duplicated()]
        h["ws_era"] = era5_wind(ERA5, lat, lon, h.index)
        h["sid"] = sid
        rows.append(h)
    m = pd.concat(rows)
    return m[(m.ws1 >= 2.0) & (m.gphys >= m.ws1) & np.isfinite(m.ws_era)]


def main():
    from gust_measured_fit import feats, fit_gumbel
    from tempest.scoring.score import crps_ensemble
    from tempest_weather import api
    m = load()
    t = pd.DatetimeIndex(m.index)
    doy, hr, yr = t.dayofyear.to_numpy(), (t.hour + t.minute / 60).to_numpy(), t.year.to_numpy()
    wo, g, era, sid = m.ws1.values, m.gphys.values, m.ws_era.values, m.sid.values
    Xe = feats(era, doy, hr, np.zeros(len(m)), "add2")[1]
    fit, val = yr <= 2020, (yr >= 2021) & (yr <= 2023)
    rng = np.random.default_rng(0)
    lines = [f"AV13 Denver gust law switched by model wind (region law at ERA5 10 m wind >= {SWITCH:g} m/s, built-in below): {len(m)} hours DEN + APA, "
             f"fit <= 2020 {int(fit.sum())}, test 2021-23 {int(val.sum())}; {M} members, same uniforms for every law"]
    cb, cs, c0, wl = [], [], [], []
    for (a, *_), (b, *_) in ((STATIONS[0], STATIONS[1]), (STATIONS[1], STATIONS[0])):
        f, o = fit & (sid == a), val & (sid == b)
        th = fit_gumbel(Xe[f], g[f])
        L = -np.log(-np.log(rng.random((int(o.sum()), M)).clip(1e-12, 1 - 1e-12)))

        def draw(mu, beta):
            return np.maximum(mu[:, None] + beta[:, None] * L, wo[o][:, None])
        xb = draw(*api._gust_physical(api.GUST_PHYS_MODEL, api.GUST_PHYS_MODEL_CAP, era[o], doy[o], hr[o], 1.0))
        x0 = draw(*api._gust_physical(api.GUST_PHYS_MODEL, api.GUST_PHYS_MODEL_CAP, era[o], doy[o], hr[o], 0.0))
        xr_ = draw(Xe[o] @ th[0], np.exp(np.clip(Xe[o] @ th[1], -6, 4)))
        xs = switch(xb, xr_, era[o])
        crps = lambda x: crps_ensemble(x[..., None], g[o][:, None])[:, 0]   # noqa: E731
        c_b, c_s, c_r, c_0 = crps(xb), crps(xs), crps(xr_), crps(x0)
        hi = era[o] >= SWITCH
        lines.append(f"  law fitted on {a}, scored on {b} 2021-23 ({int(o.sum())} hours, {int(hi.sum())} at model wind >= {SWITCH:g}): CRPS built-in flag 1 {c_b.mean():.3f}, "
                     f"flag 0 {c_0.mean():.3f}, region law everywhere {c_r.mean():.3f}, switch {c_s.mean():.3f}; >= {SWITCH:g} m/s: built-in {c_b[hi].mean():.3f}, region {c_r[hi].mean():.3f}")
        cb.append(c_b), cs.append(c_s), c0.append(c_0), wl.append(~hi)
    cb, cs, wl = np.concatenate(cb), np.concatenate(cs), np.concatenate(wl)
    gain, lo, hi_ = gain_ci(cb, cs, rng)
    g_low = 100 * (1 - cs[wl].mean() / cb[wl].mean())
    g_high, glo_h, ghi_h = gain_ci(cb[~wl], cs[~wl], rng)
    lines.append(f"  pooled cross-station: gain {gain:+.2f} % (95 % interval {lo:+.2f} to {hi_:+.2f}); below {SWITCH:g} m/s {g_low:+.3f} % ({int(wl.sum())} hours, identical by construction); "
                 f"at / above {g_high:+.2f} % [{glo_h:+.2f}, {ghi_h:+.2f}] ({int((~wl).sum())} hours)")
    lines.append("AV13 rule (pre-set): PASS = cross-station gain > 0 with interval excluding 0 AND not worse below 5 m/s; KILL = cross-station gain <= 0; else MISS.")
    lines.append("AV13 verdict: " + judge(gain, lo, hi_, g_low))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(1.0, 0.2, 1.8, 0.0).startswith("PASS")
    assert judge(1.0, -0.2, 1.8, 0.0).startswith("MISS")
    assert judge(1.0, 0.2, 1.8, -0.1).startswith("MISS")
    assert judge(-0.1, -1, 0.5, 0.0).startswith("KILL")
    x = switch(np.zeros((3, 2)), np.ones((3, 2)), np.array([4.9, 5.0, 7.0]))
    assert (x == [[0, 0], [1, 1], [1, 1]]).all()
    a = np.full(40, 2.0)
    g, lo, _ = gain_ci(a, a * 0.9, np.random.default_rng(0), 50)
    assert abs(g - 10) < 1e-9 and abs(lo - 10) < 1e-9


_selfcheck()
if __name__ == "__main__":
    main()
