"""SIGMA (New_Plan 14.3) stage 2: Mode F with the lead read as a noise level. Used by scripts/il6_modeF.py --sigma (opt-in; off = as before).

member = climate mean + beta x (forecast - climate mean) + s x F, per row and column (176 = 4 variables x 44 heights);
the network F learns (truth - base) / s, so its job has size about 1 at every lead.
beta and s / climate spread are TABLED per lead day 1..10 and column (SIGMA stage 1, 2026-11-13: the two-number exponential curves had the
wrong shape; the tabled arm B0tab is the bar). Climate mean per place x month x UTC hour of the fit rows (fallback month x hour, then all
rows); climate spread per month x column. Everything is fit on the fit rows only (years <= 2020).
"""
import numpy as np

DAYS = 10
S_FLOOR = 0.05                    # s held to >= 5 % of the climate spread, so a near-perfect column cannot blow the target up


def _flat(x):
    x = np.asarray(x)
    return x.reshape(len(x), -1).astype(np.float32)


def _keys(d):
    month = np.asarray(d["valid"]).astype("datetime64[M]").astype(np.int64) % 12
    place = np.round(np.asarray(d["lat"], float), 3) * 1e4 + np.round(np.asarray(d["lon"], float), 3)
    return place, month, np.asarray(d["valid_utc_hour"]).astype(np.int64)


def lead_day(lead_days):
    """0.25-1.0 -> 1, ..., 9.25-10 -> 10 (and beyond 10 -> 10)."""
    return np.clip(np.ceil(np.asarray(lead_days, float) - 1e-6), 1, DAYS).astype(int)


def _group_mean(x, inv, n):
    s = np.zeros((n, x.shape[1]))
    np.add.at(s, inv, x)
    return s / np.bincount(inv, minlength=n)[:, None]


def _climate_mean(tab, d):
    place, month, hour = _keys(d)
    out = np.empty((len(place), tab["mean_all"].shape[0]), np.float32)
    for i, (p, m, h) in enumerate(zip(place.tolist(), month.tolist(), hour.tolist())):
        j = tab["pos3"].get((p, m, h))
        if j is not None:
            out[i] = tab["mean3"][j]
        else:
            j = tab["pos2"].get(m * 24 + h)
            out[i] = tab["mean2"][j] if j is not None else tab["mean_all"]
    return out, month


def fit(d):
    """fit rows (dict: obs, hres, valid, lat, lon, valid_utc_hour, lead_days, year) -> tables."""
    assert np.asarray(d["year"]).max() <= 2020, "SIGMA tables only from fit years <= 2020"
    obs, hres = _flat(d["obs"]), _flat(d["hres"])
    place, month, hour = _keys(d)
    u3, inv3 = np.unique(np.stack([place, month, hour], 1), axis=0, return_inverse=True)
    inv3 = inv3.ravel()
    u2, inv2 = np.unique(month * 24 + hour, return_inverse=True)
    tab = dict(mean3=_group_mean(obs, inv3, len(u3)).astype(np.float32), mean2=_group_mean(obs, inv2.ravel(), len(u2)).astype(np.float32),
               mean_all=obs.mean(0), pos3={(float(p), int(m), int(h)): i for i, (p, m, h) in enumerate(u3)}, pos2={int(k): i for i, k in enumerate(u2)})
    cm = tab["mean3"][inv3]
    anom = obs - cm
    csd = np.stack([anom[month == m].std(0) if (month == m).sum() > 1 else anom.std(0) for m in range(12)])
    tab["csd"] = np.maximum(csd, 1e-6).astype(np.float32)                   # (12, C)
    fa, ld, crow = hres - cm, lead_day(d["lead_days"]), tab["csd"][month]
    C = obs.shape[1]
    beta, srel, have = np.ones((DAYS, C), np.float32), np.ones((DAYS, C), np.float32), np.zeros(DAYS, bool)
    for i in range(DAYS):
        k = ld == i + 1
        if k.sum() < 100:
            continue
        x, y = fa[k].astype(float), anom[k].astype(float)
        beta[i] = np.clip((x * y).mean(0) / np.maximum((x * x).mean(0), 1e-9), 0, 1.2)
        srel[i] = np.sqrt(((y - beta[i] * x) ** 2).mean(0) / (crow[k].astype(float) ** 2).mean(0))
        have[i] = True
    assert have.any(), "no lead day with 100 fit rows"
    ok = np.flatnonzero(have)
    for i in np.flatnonzero(~have):                                         # a lead day without rows takes the nearest fitted day
        j = ok[np.abs(ok - i).argmin()]
        beta[i], srel[i] = beta[j], srel[j]
    tab["beta"], tab["srel"] = beta, np.maximum(srel, S_FLOOR)
    return tab


def nest_widths(tab, width):
    """NEST (stage 3): hidden width per lead day, width x (4 - 3 x (s_d - s_min) / (s_max - s_min)) / 4 in quarters; s_d = mean srel of day d."""
    s = tab["srel"].mean(1)
    q = np.rint(4 - 3 * (s - s.min()) / max(s.max() - s.min(), 1e-9)).astype(int)
    return [int(width * k // 4) for k in q]


def base_scale(tab, d):
    """-> base (n, C) = climate + beta x forecast anomaly, s (n, C)."""
    cm, month = _climate_mean(tab, d)
    i = lead_day(d["lead_days"]) - 1
    return cm + tab["beta"][i] * (_flat(d["hres"]) - cm), tab["srel"][i] * tab["csd"][month]


def target(tab, d):
    base, s = base_scale(tab, d)
    return ((_flat(d["obs"]) - base) / s).astype(np.float32)


def to_residual(tab, d, f):
    """network draws f (n, m, C) in SIGMA units -> residual samples (member - forecast), the form modeF.to_physical takes."""
    base, s = base_scale(tab, d)
    return base[:, None] + s[:, None] * f - _flat(d["hres"])[:, None]
