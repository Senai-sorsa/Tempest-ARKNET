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


# UR2 stage 5 (New_Plan 17, opt-in): the IFS-ensemble spread scales s. The 24 `ens` features of data/modeF_ens (scripts/il14_ens_rows.py) are
# (mean, sd) pairs: u10, v10, t2m, then u, v, t at 500 / 700 / 850 hPa. Column -> sd feature by variable and height above ground: below 500 m the
# 10 m / 2 m feature, 500 m - 2.5 km the 700 hPa one, above that 500 hPa (850 hPa lies near or below the ground in the NM/TX and Denver boxes);
# RH has no ensemble feature (factor 1). Shortcut: the height bands are fixed, not from each row's pressure.
ENS_SD = {("u", 0): 1, ("v", 0): 3, ("T", 0): 5, ("u", 500): 7, ("u", 700): 9, ("v", 500): 13, ("v", 700): 15, ("T", 500): 19, ("T", 700): 21}
ENS_CLIP = (0.8, 1.5)


def ens_columns():
    """-> (C,) index of the ensemble sd feature for each of the 176 columns, -1 = none."""
    from tempest.forecast.modeF import HEIGHTS, PROFILE
    out = []
    for v in PROFILE:
        for h in HEIGHTS:
            lev = 0 if h < 500 else 700 if h < 2500 else 500
            out.append(ENS_SD.get((v, lev), -1))
    return np.asarray(out, int)


def _ens_factor(tab, d, i):
    """ens spread / its fit-row median for the row's lead day, per column, held to ENS_CLIP; 1 where there is no feature."""
    col = tab["ens_col"]
    sd = np.asarray(d["ens"], np.float32)[:, np.maximum(col, 0)]
    f = np.clip(sd / np.maximum(tab["ens_med"][i][:, np.maximum(col, 0)], 1e-6), *ENS_CLIP)
    return np.where(col[None, :] >= 0, f, 1.0).astype(np.float32)


def fit(d, ens_scale=False):
    """fit rows (dict: obs, hres, valid, lat, lon, valid_utc_hour, lead_days, year) -> tables.
    ens_scale (UR2 stage 5, opt-in; False = as before): rows need `ens`; adds the per-lead-day median of each ensemble feature, and s is then
    scaled per row by ens sd / median (base_scale). The tables beta and srel are fitted with that scale in place, so s stays the right size."""
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
    if ens_scale:
        e = np.asarray(d["ens"], np.float32)
        med_all = np.median(e, 0)
        tab["ens_med"] = np.stack([np.median(e[ld == i + 1], 0) if (ld == i + 1).sum() >= 20 else med_all for i in range(DAYS)]).astype(np.float32)
        tab["ens_col"] = ens_columns()
        crow = crow * _ens_factor(tab, d, ld - 1)                            # s is fitted on the scaled climate spread
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
    s = tab["srel"][i] * tab["csd"][month]
    if "ens_med" in tab:                                                     # UR2 stage 5 (only when fit(..., ens_scale=True))
        s = s * _ens_factor(tab, d, i)
    return cm + tab["beta"][i] * (_flat(d["hres"]) - cm), s


def target(tab, d):
    base, s = base_scale(tab, d)
    return ((_flat(d["obs"]) - base) / s).astype(np.float32)


def to_residual(tab, d, f):
    """network draws f (n, m, C) in SIGMA units -> residual samples (member - forecast), the form modeF.to_physical takes."""
    base, s = base_scale(tab, d)
    return base[:, None] + s[:, None] * f - _flat(d["hres"])[:, None]
