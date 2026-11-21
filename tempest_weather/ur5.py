"""WD1 (New_Plan 19 WD1, b29 UR5 + b40 spread refit, PASS 2026-11-15; tool port New_Plan 28.11 item 12): 10 m wind fix for climate-mode sequences.
Per hour of a sequence, at the nearest table point and the hour's month / UTC hour:
  1. speed quantile map of the tool's 10 m speed to ERA5 (fit 1991-2005), direction kept (b29 speed_map / apply_map);
  2. u and v scaled around the hour's member mean by s_u, s_v (b40 scale);
  3. hours after the first are re-ordered by a two-regime Gaussian chain on the 10 m speed (b29 regime_link): correlation rho_calm below the previous
     hour's ERA5 median, rho_windy above, rho ** gap for a gap of several hours; each hour's member set is unchanged (only which member gets which 10 m wind).
Only the 10 m level (column 0) moves here; the tool (api.atmosphere_sequence) fades the 10 m change out by 300 m so the 10-50 m shear stays as ERA5's. A table cell without a fit (outside the served hours) leaves that hour as it is and restarts the chain there.
Table (asset post/ur5_*): lat, lon (P,), xt, xe (P, 12, 24, Q) map knots, ok (P, 12, 24), rho (P, 12, 24, 3) = rho_calm, rho_windy, median, s (2,) = s_u, s_v.
"""
import numpy as np
from scipy.stats import norm

QS = np.linspace(0.005, 0.995, 100)


def fit_map(tool_s, era_s):
    """-> (xt, xe) knots of the quantile map tool speed -> ERA5 speed (linear between, flat beyond)."""
    xt, xe = np.quantile(tool_s, QS), np.quantile(era_s, QS)
    return np.maximum.accumulate(xt + np.arange(len(xt)) * 1e-9), xe


def apply_map(u, v, xt, xe):
    s = np.hypot(u, v)
    k = np.where(s > 1e-6, np.interp(s, xt, xe) / np.maximum(s, 1e-6), 1.0)
    return u * k, v * k


def regime_rho(tpl):
    """real 3-hour windows (k, 3) -> (rho calm, rho windy, median of hour 0) of the normal scores of consecutive hours."""
    z = norm.ppf((np.argsort(np.argsort(tpl, 0), 0) + 0.5) / len(tpl))
    med = np.median(tpl[:, 0])
    r = []
    for sel in (tpl[:, 0] < med, tpl[:, 0] >= med):
        a = np.concatenate([z[sel, 0], z[sel, 1]])
        b = np.concatenate([z[sel, 1], z[sel, 2]])
        r.append(float(np.corrcoef(a, b)[0, 1]))
    return r[0], r[1], float(med)


def scale(x, s):
    m = x.mean()
    return m + s * (x - m)


def nearest(T, lat, lon):
    return int(np.argmin((T["lat"] - lat) ** 2 + (T["lon"] - lon) ** 2))


def apply(T, p, times, us, vs, rng, anchor=False):
    """T table, p table point, times: list of naive UTC datetimes (one per hour), us / vs: lists of (n,) 10 m u, v.
    anchor=False: the chain's new-hour noise is random (b29 regime_link). anchor=True (tool default): the noise is each member's own 10 m rank score at that hour with the part explained
    by the chain removed, and only the speed moves (each member keeps its own 10 m direction), so the chain keeps its lag correlation but each member's 10 m moves as little as possible (the 10 m stays paired with its own column above; b89 found
    random re-ordering of the 10 m alone sends the 10-50 m shear p50 from 18 to 115 m/s per km).
    -> (us', vs', perms): new 10 m winds and, per hour, the member permutation applied by the chain (None = order kept)."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    su, sv = float(T["s"][0]), float(T["s"][1])
    us, vs, perms = [np.asarray(u, float).copy() for u in us], [np.asarray(v, float).copy() for v in vs], [None] * len(times)
    for i in order:
        m, h = times[i].month - 1, times[i].hour
        if T["ok"][p, m, h]:
            u, v = apply_map(us[i], vs[i], T["xt"][p, m, h], T["xe"][p, m, h])
            us[i], vs[i] = scale(u, su), scale(v, sv)
    z = prev = prev_t = None
    for i in order:
        t = times[i]
        n = len(us[i])
        w = np.hypot(us[i], vs[i])
        gap = None if prev_t is None else (t - prev_t).total_seconds() / 3600.0
        mp, hp = (prev_t.month - 1, prev_t.hour) if prev_t is not None else (None, None)
        if z is None or not T["ok"][p, t.month - 1, t.hour] or not T["ok"][p, mp, hp] or not 0 < gap <= 6:
            z = norm.ppf((np.argsort(np.argsort(w)) + 0.5) / n)            # chain (re)starts: this hour keeps its order
        else:
            rc, rw, med = T["rho"][p, mp, hp]
            rho = np.where(prev < med, rc, rw) ** gap
            if anchor:
                c = norm.ppf((np.argsort(np.argsort(w)) + 0.5) / n)
                r = np.corrcoef(c, z)[0, 1]
                e = c - r * z
                e = e / max(e.std(), 1e-9)
            else:
                e = rng.standard_normal(n)
            z = rho * z + np.sqrt(1 - rho ** 2) * e
            perm = np.argsort(w)[np.argsort(np.argsort(z))]
            if anchor:                                                     # speed only: each member keeps its own 10 m direction
                k = np.where(w > 1e-6, w[perm] / np.maximum(w, 1e-6), 1.0)
                us[i], vs[i] = np.where(w > 1e-6, us[i] * k, us[i][perm]), np.where(w > 1e-6, vs[i] * k, vs[i][perm])
            else:
                us[i], vs[i] = us[i][perm], vs[i][perm]
            perms[i] = perm
            w = w[perm]
        prev, prev_t = w, t
    return us, vs, perms


def _selfcheck():
    from datetime import datetime
    rng = np.random.default_rng(0)
    a, b = rng.gamma(4, 1.6, 4000), rng.gamma(4, 1.3, 4000)
    xt, xe = fit_map(a, b)
    assert abs(np.median(np.interp(a, xt, xe)) - np.median(b)) < 0.1
    u2, v2 = apply_map(np.array([3.0, 0.0]), np.array([4.0, 0.0]), np.array([0.0, 10.0]), np.array([0.0, 5.0]))
    assert np.allclose([u2[0], v2[0]], [1.5, 2.0]) and u2[1] == 0
    # chain = b29 regime_link (same rng draws) when the map is the identity and s = 1
    T = dict(lat=np.zeros(1), lon=np.zeros(1), xt=np.tile(np.linspace(0, 50, 100), (1, 12, 24, 1)), xe=np.tile(np.linspace(0, 50, 100), (1, 12, 24, 1)),
             ok=np.ones((1, 12, 24), bool), rho=np.tile([0.6, 0.9, 4.0], (1, 12, 24, 1)), s=np.ones(2))
    uu, vv = rng.normal(3, 2, (3, 500)), rng.normal(1, 2, (3, 500))
    ts = [datetime(2013, 7, 15, 15 + k) for k in range(3)]
    ou, ov, _ = apply(T, 0, ts, list(uu), list(vv), np.random.default_rng(5))
    w3, r2 = np.hypot(uu, vv), np.random.default_rng(5)
    zz, prev, ref = norm.ppf((np.argsort(np.argsort(w3[0])) + 0.5) / 500), w3[0], [w3[0]]
    for h in (1, 2):
        rho = np.where(prev < 4.0, 0.6, 0.9)
        zz = rho * zz + np.sqrt(1 - rho ** 2) * r2.standard_normal(500)
        ref.append(np.sort(w3[h])[np.argsort(np.argsort(zz))])
        prev = ref[-1]
    assert np.allclose(np.hypot(ou, ov), np.array(ref)), "chain differs from b29 regime_link"
    for k in range(3):                                                      # each hour keeps its member set (pairs u, v moved together)
        assert np.allclose(np.sort(ou[k] + 1j * ov[k]), np.sort(uu[k] + 1j * vv[k]))
    au, av, _ = apply(T, 0, ts, list(uu), list(vv), np.random.default_rng(5), anchor=True)   # tool mode: speed set kept, each member keeps its direction
    for k in range(3):
        assert np.allclose(np.sort(np.hypot(au[k], av[k])), np.sort(w3[k]))
        assert np.allclose(np.arctan2(av[k], au[k]), np.arctan2(vv[k], uu[k]))


_selfcheck()
