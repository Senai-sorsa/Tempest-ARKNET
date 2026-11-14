"""Earth-GRAM comparison kit: coupling, shape and accuracy of ANY set of atmospheres against real balloons. REPORT ONLY (changes nothing in the tool).
Purpose: one scorer that treats every source the same way, so real Earth-GRAM output can be dropped in later and compared with the tool on the same cases.

Sources (each gives m whole profiles of u, v, T, p on the 44 model heights for every case):
  tool        the installed tool, climate mode (kit_common.tool), made here
  gaussfull   --standin: bell curve with the station's own balloon mean and FULL covariance of u, v, T over all heights (1991-2020, same month and hour),
              p from the drawn surface pressure by the hydrostatic rule. NOT Earth-GRAM: it is the ceiling for any bell-curve method at a balloon station.
              It is written to data/kit/gram_gaussfull.npz and read back through the external path, so that path is exercised today.
  bank        --bank (E5, New_Plan 16): m real balloon profiles of the same station, calendar month and UTC hour, 1991-2020, drawn without repeats from the complete
              ones (u, v, T, p at all 44 heights). The measured-profile bar: true shear, layers and coupling by construction, no skill beyond climatology.
              Written to data/kit/gram_bank.npz and read back through the external path like gaussfull. Report only, no rule.
  external    --extra NAME=FILE.npz, any number of times (real Earth-GRAM later). File format: `case` (n,) strings "<station id>|YYYY-MM-DDTHH" as in the
              case list, and `u`, `v` [m/s], `T` [K], `p` [Pa], each (n, members, 44) on the model heights above ground. Make it from a long CSV
              (columns case, member, height_m [above ground], u, v, T, p; any heights that span 10 m - 18 km) with --from-csv IN.csv OUT.npz.
Truth: IGRA balloons at Santa Teresa (EPZ) and Midland (MAF), 00Z and 12Z, 2024-25 (the development window; never 2026). --cases-out FILE.csv writes the
case list (station, lat, lon, elevation, UTC time) and FILE_heights.csv (the 44 heights above ground and above sea level per station): the runs to make
in Earth-GRAM. Only cases that every source holds are scored; all sources are cut to the same number of members (CRPS depends on it).

Scores (lower is better unless a target is named):
  accuracy   CRPS of u, v, T (mean of the four height bands); 90 % and 99 % range coverage (targets 0.90, 0.99)
  coupling   VS: variogram score (p 0.5) of each profile, i.e. differences between heights; VSx: variogram score between u, v, T, ln p at the SAME height
             (each divided by the balloon spread), i.e. the link between variables; vertical-correlation error and cross-variable correlation error
             (one member per case against the balloons, departures from the 1991-2020 balloon mean; both carry sampling noise, so read the
             'POOLED source minus tool' lines, where it cancels, not the single values)
  shape      shear p50 / p99 ratio to balloons per band (target 1); share of layers with Richardson number < 1 per band (target = balloon row);
             co-extremes P(10 m speed and 10 m - 1 km shear both above their q95) / 0.05 (target = balloon row); band-depth histogram deviation of u, v, T
  physics    hydrostatic gap: median |p above / p expected from p below and the layer T - 1|, in % (dry air; the balloon row is the floor)

Reading rule (set 2026-11-12, before any real Earth-GRAM output exists): for the paired scores (CRPS, VS, VSx) a source is better than the tool only when the
day-block interval of (source - tool) is below 0, worse only when above 0, otherwise a tie. The pooled scores (two correlation errors, co-extreme distance
to the balloon value) are read the same way from the day-bootstrap interval of (source - tool). Shear, Ri and depth rows have no interval: they are
descriptive, and a difference under the noise named in the notes is not a result. Every score where the tool is not better is reported; no score is dropped after seeing the result.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_gram_compare.py --standin                    # 200 cases per group, about 25 min
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_gram_compare.py --standin --per-group 4 --m 40   # smoke test
    ... --extra gram=data/kit/earthgram.npz          ... --cases-out data/kit/gram_cases.csv          ... --from-csv IN.csv OUT.npz
Result: docs/results/logs/kit_b9_gram_compare.log
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K
from b1_shape_scores import depth_bin, ri_counts

VARS = ("u", "v", "T")
J1 = list(K.H).index(1000.0)
RD, G = 287.05, 9.81
BIDX = [K.band_idx(lo, hi) for _, lo, hi in K.BANDS]
MIDB = [np.flatnonzero((0.5 * (K.H[1:] + K.H[:-1]) >= lo) & (0.5 * (K.H[1:] + K.H[:-1]) < hi)) for _, lo, hi in K.BANDS]


def crps_cols(ens, y):
    """CRPS per column: ens (m, D), y (D,) -> (D,), NaN where y is NaN."""
    e = np.sort(ens, 0)
    m = len(e)
    w = (2 * np.arange(1, m + 1) - m - 1)[:, None]
    return np.abs(e - y).mean(0) - (w * e).sum(0) / (m * m)


def vs_profile(ens, y, p=0.5):
    """Variogram score of one profile, mean per pair of heights. ens (m, D), y (D,) with NaN allowed."""
    ok = np.isfinite(y)
    if ok.sum() < 2:
        return np.nan
    x, yy = ens[:, ok], y[ok]
    vy = np.abs(yy[:, None] - yy[None, :]) ** p
    vx = (np.abs(x[:, :, None] - x[:, None, :]) ** p).mean(0)
    return float(((vy - vx) ** 2).sum() / (ok.sum() * (ok.sum() - 1)))


def vs_cross(ens, y, p=0.5):
    """Variogram score between variables at the same height, mean per variable pair and height. ens (m, V, D) and y (V, D), already scaled."""
    ok = np.isfinite(y).all(0)
    if not ok.any():
        return np.nan
    x, yy = ens[:, :, ok], y[:, ok]
    vy = np.abs(yy[:, None] - yy[None, :]) ** p
    vx = (np.abs(x[:, :, None] - x[:, None]) ** p).mean(0)
    nv = len(yy)
    return float(((vy - vx) ** 2).sum() / (nv * (nv - 1) * ok.sum()))


def hydro_gap(T, p):
    """|p above / p expected from p below and the layer-mean T - 1| per layer, (..., 43)."""
    tbar = 0.5 * (T[..., 1:] + T[..., :-1])
    return np.abs(p[..., 1:] / (p[..., :-1] * np.exp(-G * np.diff(K.H) / (RD * tbar))) - 1.0)


def coext(u, v, q=0.95):
    """P(10 m speed and 10 m - 1 km vector shear both above their own q) / (1 - q): 1 = always together, 1 - q = independent. Rows (n, 44)."""
    w, sh = np.hypot(u[:, 0], v[:, 0]), np.hypot(u[:, J1] - u[:, 0], v[:, J1] - v[:, 0])
    ok = np.isfinite(w) & np.isfinite(sh)
    if ok.sum() < 40:
        return np.nan
    w, sh = w[ok], sh[ok]
    return float(((w > np.quantile(w, q)) & (sh > np.quantile(sh, q))).mean() / (1 - q))


_CLIM = {}


def clim(sid, month, hour):
    """Balloons of one station, calendar month and UTC hour, 1991-2020 -> dict u, v, T, lnp (rows, 44)."""
    key = (sid, month, hour)
    if key not in _CLIM:
        t, b = K.balloon(sid)
        sel = (t.year >= 1991) & (t.year <= 2020) & (t.month == month) & (t.hour == hour)
        _CLIM[key] = {"u": b["u"][sel], "v": b["v"][sel], "T": b["T"][sel], "lnp": np.log(b["p"][sel])}
    return _CLIM[key]


def clim_stats(sid, month, hour):
    c = clim(sid, month, hour)
    with np.errstate(all="ignore"):
        return {k: np.nanmean(x, 0) for k, x in c.items()}, {k: np.nanstd(x, 0) + 1e-9 for k, x in c.items()}


def cases(per_group, rng):
    """-> list of (case id, station id, time, balloon dict of (44,))."""
    out = []
    for sid in (K.EPZ, K.MAF):
        t, b = K.balloon(sid)
        full = np.isfinite(b["u"]).sum(1) >= 30
        for hour in (0, 12):
            idx = np.flatnonzero((t.year >= 2024) & (t.year <= 2025) & (t.hour == hour) & full)
            for k in rng.permutation(idx)[:per_group]:
                assert K.day_ok(t[k])
                out.append((f"{sid}|{t[k]:%Y-%m-%dT%H}", sid, t[k], {q: b[q][k] for q in b}))
    return out


def gauss_members(sid, month, hour, m, rng):
    """m draws of u, v, T (m, 44) and p from the balloon mean + full covariance (pairwise over missing values, made positive by clipping eigenvalues)."""
    c = clim(sid, month, hour)
    x = pd.DataFrame(np.hstack([c["u"], c["v"], c["T"], c["lnp"][:, :1]]))
    mu, cov = x.mean().values, x.cov(min_periods=20).fillna(0.0).values
    val, vec = np.linalg.eigh(0.5 * (cov + cov.T))
    d = mu + (rng.standard_normal((m, len(mu))) * np.sqrt(np.clip(val, 0.0, None))) @ vec.T
    u, v, T, lnp0 = d[:, :K.NH], d[:, K.NH:2 * K.NH], d[:, 2 * K.NH:3 * K.NH], d[:, -1]
    tbar = 0.5 * (T[:, 1:] + T[:, :-1])
    lnp = lnp0[:, None] + np.hstack([np.zeros((m, 1)), np.cumsum(-G * np.diff(K.H) / (RD * tbar), 1)])
    return {"u": u, "v": v, "T": T, "p": np.exp(lnp)}


def build_standin(todo, m, rng):
    path = os.path.join(K.OUT, "gram_gaussfull.npz")
    os.makedirs(K.OUT, exist_ok=True)
    mem = [gauss_members(sid, t.month, t.hour, m, rng) for _, sid, t, _ in todo]
    np.savez_compressed(path, case=np.array([c[0] for c in todo]), **{k: np.stack([x[k] for x in mem]).astype(np.float32) for k in ("u", "v", "T", "p")})
    return path


def bank_members(sid, month, hour, m, rng):
    """m complete balloon profiles of one station, calendar month and UTC hour, 1991-2020, without repeats -> dict u, v, T, p (m, 44)."""
    c = clim(sid, month, hour)
    ok = np.flatnonzero(np.isfinite(np.hstack([c["u"], c["v"], c["T"], c["lnp"]])).all(1))
    assert len(ok) >= m, f"{sid} month {month} hour {hour}: only {len(ok)} complete balloons for {m} members"
    k = rng.choice(ok, m, replace=False)
    return {"u": c["u"][k], "v": c["v"][k], "T": c["T"][k], "p": np.exp(c["lnp"][k])}


def build_bank(todo, m, rng):
    path = os.path.join(K.OUT, "gram_bank.npz")
    os.makedirs(K.OUT, exist_ok=True)
    mem = [bank_members(sid, t.month, t.hour, m, rng) for _, sid, t, _ in todo]
    np.savez_compressed(path, case=np.array([c[0] for c in todo]), **{k: np.stack([x[k] for x in mem]).astype(np.float32) for k in ("u", "v", "T", "p")})
    return path


def load_external(path):
    """-> (dict case id -> row, dict u, v, T, p of (n, members, 44))."""
    d = np.load(path, allow_pickle=False)
    arr = {k: d[k] for k in ("u", "v", "T", "p")}
    for k, x in arr.items():
        assert x.ndim == 3 and x.shape[2] == K.NH and x.shape[0] == len(d["case"]), f"{path}: {k} must be (cases, members, {K.NH}), got {x.shape}"
    assert 150 < np.nanmedian(arr["T"]) < 330 and 3e3 < np.nanmedian(arr["p"]) < 1.1e5, f"{path}: T must be in K and p in Pa"
    return {str(c): i for i, c in enumerate(d["case"])}, arr


def csv_to_npz(src, out):
    """Long table (case, member, height_m above ground, u, v, T, p) -> the external npz on the 44 model heights (linear in height; p in log)."""
    d = pd.read_csv(src)
    missing = {"case", "member", "height_m", "u", "v", "T", "p"} - set(d.columns)
    assert not missing, f"columns missing: {sorted(missing)}"
    ids, mem = sorted(d["case"].astype(str).unique()), sorted(d["member"].unique())
    ci, mi = {c: i for i, c in enumerate(ids)}, {x: i for i, x in enumerate(mem)}
    arr = {k: np.full((len(ids), len(mem), K.NH), np.nan, np.float32) for k in ("u", "v", "T", "p")}
    for (c, x), g in d.groupby([d["case"].astype(str), "member"]):
        g = g.sort_values("height_m")
        z = g["height_m"].values.astype(float)
        assert z[0] <= K.H[0] + 1.0 and z[-1] >= K.H[-1] - 1.0, f"case {c} member {x}: heights {z[0]:.0f}-{z[-1]:.0f} m do not span {K.H[0]:.0f}-{K.H[-1]:.0f} m above ground"
        for k in ("u", "v", "T"):
            arr[k][ci[c], mi[x]] = np.interp(K.H, z, g[k].values)
        arr["p"][ci[c], mi[x]] = np.exp(np.interp(K.H, z, np.log(g["p"].values)))
    np.savez_compressed(out, case=np.array(ids), **arr)
    return len(ids), len(mem)


def write_cases(todo, path):
    rows, hrows = [], []
    for cid, sid, t, _ in todo:
        lat, lon, elev = K.station_pos(sid)
        rows.append(dict(case=cid, station=sid, lat=lat, lon=lon, elevation_m=elev, time_utc=f"{t:%Y-%m-%d %H:%M}", month=t.month))
    for sid in sorted({c[1] for c in todo}):
        elev = K.station_pos(sid)[2]
        hrows += [dict(station=sid, height_above_ground_m=h, height_above_sea_m=h + elev) for h in K.H]
    pd.DataFrame(rows).to_csv(path, index=False)
    pd.DataFrame(hrows).to_csv(os.path.splitext(path)[0] + "_heights.csv", index=False)


def per_case(mem, b, mu, sd):
    """Paired scores of one case. mem: dict u, v, T, p (m, 44); b: balloon dict (44,)."""
    row = {}
    for q in VARS:
        c = crps_cols(mem[q], b[q])
        lo, hi = np.percentile(mem[q], [5, 95], axis=0)
        lo2, hi2 = np.percentile(mem[q], [0.5, 99.5], axis=0)
        ok = np.isfinite(b[q])
        with np.errstate(all="ignore"):
            row["crps_" + q] = float(np.nanmean([np.nanmean(c[i]) for i in BIDX]))
        row["cov90_" + q] = float(((b[q] >= lo) & (b[q] <= hi))[ok].mean())
        row["cov99_" + q] = float(((b[q] >= lo2) & (b[q] <= hi2))[ok].mean())
        row["vs_" + q] = vs_profile(mem[q], b[q])
    zs = np.stack([(mem[q] - mu[q]) / sd[q] for q in VARS] + [(np.log(mem["p"]) - mu["lnp"]) / sd["lnp"]], 1)
    zy = np.stack([(b[q] - mu[q]) / sd[q] for q in VARS] + [(np.log(b["p"]) - mu["lnp"]) / sd["lnp"]])
    row["vsx"] = vs_cross(zs, zy)
    return row


def offdiag_err(a, b):
    m = ~np.eye(len(a), dtype=bool)
    return float(np.nanmean(np.abs(a - b)[m]))


def vert_err(src, tru):
    """Mean |vertical correlation of the source - of the balloons| over u, v, T. src, tru: dict q -> (n, 44) departures; the source is hidden where the balloon is."""
    out = []
    for q in VARS:
        s = np.where(np.isfinite(tru[q]), src[q], np.nan)
        out.append(offdiag_err(pd.DataFrame(s).corr(min_periods=30).values, pd.DataFrame(tru[q]).corr(min_periods=30).values))
    return float(np.mean(out))


def cross_err(src, tru):
    """Mean |correlation between u, v, T, ln p at one height: source - balloons|, over the heights with at least 30 complete balloon rows."""
    out = []
    for h in range(K.NH):
        t = np.stack([tru[q][:, h] for q in (*VARS, "lnp")], 1)
        ok = np.isfinite(t).all(1)
        if ok.sum() < 30:
            continue
        s = np.stack([src[q][ok, h] for q in (*VARS, "lnp")], 1)
        out.append(offdiag_err(np.corrcoef(s, rowvar=False), np.corrcoef(t[ok], rowvar=False)))
    return float(np.mean(out)) if out else np.nan


def boot(fn, days, draws, seed=0):
    """fn(row indices) -> number. -> (value on all rows, lo, hi) from resampling whole days."""
    uniq, inv = np.unique(np.asarray(days), return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    vals = [fn(np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))])) for _ in range(draws)]
    return fn(np.arange(len(days))), float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=200, help="balloons per station x hour (4 groups)")
    ap.add_argument("--m", type=int, default=100, help="members made per case for the tool and the stand-in")
    ap.add_argument("--standin", action="store_true", help="add the full-covariance bell curve (written to data/kit, read back as an external source)")
    ap.add_argument("--bank", action="store_true", help="E5: add the measured-profile bank (written to data/kit, read back as an external source)")
    ap.add_argument("--extra", action="append", default=[], metavar="NAME=FILE.npz")
    ap.add_argument("--cases-out", metavar="FILE.csv", help="write the case list for Earth-GRAM runs and stop")
    ap.add_argument("--from-csv", nargs=2, metavar=("IN.csv", "OUT.npz"), help="convert a long table to the external format and stop")
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    if a.from_csv:
        print("wrote %s: %d cases, %d members" % (a.from_csv[1], *csv_to_npz(*a.from_csv)))
        return
    rng = np.random.default_rng(0)
    todo = cases(a.per_group, rng)
    if a.cases_out:
        write_cases(todo, a.cases_out)
        print(f"wrote {a.cases_out} ({len(todo)} cases) and its _heights.csv")
        return
    extras = [x.split("=", 1) for x in a.extra]
    if a.standin:
        extras.insert(0, ["gaussfull", build_standin(todo, a.m, np.random.default_rng(1))])
    if a.bank:
        extras.insert(1 if a.standin else 0, ["bank", build_bank(todo, a.m, np.random.default_rng(2))])
    ext = {name: load_external(path) for name, path in extras}
    names = ["tool"] + list(ext)
    m = min([a.m] + [arr["u"].shape[1] for _, arr in ext.values()])
    rows = {s: [] for s in names}
    pick = {s: {q: [] for q in (*VARS, "lnp")} for s in ["balloons"] + names}       # one profile per case, departures from the balloon mean
    raw = {s: {q: [] for q in ("u", "v")} for s in ["balloons"] + names}          # raw winds for the co-extremes: the balloon, and all members of a source
    shear = {s: [] for s in ["balloons"] + names}
    ri = {s: np.zeros((4, 2)) for s in ["balloons"] + names}
    hyd = {s: [] for s in ["balloons"] + names}
    hist = {s: {q: np.zeros(10) for q in VARS} for s in names}
    days, skipped, absent = [], 0, 0
    for cid, sid, t, b in todo:
        if any(cid not in idx for idx, _ in ext.values()):
            absent += 1
            continue
        lat, lon, elev = K.station_pos(sid)
        try:
            atm = K.tool(lat, lon, t, seed=1000 * t.year + int(t.dayofyear), n=a.m, elevation=elev)
        except ValueError:        # hour outside what the installed assets cover
            skipped += 1
            continue
        mems = {"tool": {q: np.asarray(atm[q], float) for q in (*VARS, "p")}}
        for s, (idx, arr) in ext.items():
            mems[s] = {q: arr[q][idx[cid]].astype(float) for q in (*VARS, "p")}
        mu, sd = clim_stats(sid, t.month, t.hour)
        days.append(f"{t:%Y-%m-%d}")
        tr = {**{q: b[q] for q in VARS}, "lnp": np.log(b["p"])}
        for q in (*VARS, "lnp"):
            pick["balloons"][q].append(tr[q] - mu[q])
        for q in ("u", "v"):
            raw["balloons"][q].append(b[q])
        shear["balloons"].append(K.shear_mag(b["u"], b["v"])[None])
        ri["balloons"] += ri_counts(b["u"], b["v"], b["T"], b["p"])
        hyd["balloons"].append(hydro_gap(b["T"], b["p"]))
        for s in names:
            x = {q: v[rng.permutation(len(v))[:m]] for q, v in mems[s].items()}
            rows[s].append(per_case(x, b, mu, sd))
            j = int(rng.integers(m))
            for q in VARS:
                pick[s][q].append(x[q][j] - mu[q])
                bin_ = depth_bin(x[q], b[q], rng)
                if bin_ is not None:
                    hist[s][q][bin_] += 1
            pick[s]["lnp"].append(np.log(x["p"][j]) - mu["lnp"])
            for q in ("u", "v"):
                raw[s][q].append(x[q])
            shear[s].append(K.shear_mag(x["u"], x["v"]))
            ri[s] += ri_counts(x["u"], x["v"], x["T"], x["p"])
            hyd[s].append(hydro_gap(x["T"], x["p"]).ravel())
    n = len(days)
    assert n >= 8, f"only {n} cases left"
    days = np.array(days)
    pick = {s: {q: np.array(v) for q, v in d.items()} for s, d in pick.items()}
    raw = {s: {q: np.array(v) for q, v in d.items()} for s, d in raw.items()}
    tab = {s: pd.DataFrame(rows[s]) for s in names}
    L = [f"Earth-GRAM comparison kit: {n} cases scored ({skipped} skipped: hour not covered, {absent} not in every external file), {m} members per case, sources: {', '.join(names)}",
         "ACCURACY (paired, mean over cases)      CRPS u    v     T      cov90 u  v     T      cov99 u  v     T"]
    for s in names:
        t = tab[s].mean()
        L.append(f"  {s:<36}" + "".join(f"{t['crps_' + q]:<6.3f}" for q in VARS) + "   " + "".join(f"{t['cov90_' + q]:<6.3f}" for q in VARS) + "   " + "".join(f"{t['cov99_' + q]:<6.3f}" for q in VARS))
    every = np.arange(n)
    pooled = {"vertical-corr error": lambda s, i: vert_err({q: pick[s][q][i] for q in VARS}, {q: pick["balloons"][q][i] for q in VARS}),
              "cross-variable corr error": lambda s, i: cross_err({q: x[i] for q, x in pick[s].items()}, {q: x[i] for q, x in pick["balloons"].items()}),
              "co-extreme distance to balloons": lambda s, i: abs(coext(raw[s]["u"][i].reshape(-1, K.NH), raw[s]["v"][i].reshape(-1, K.NH)) - coext(raw["balloons"]["u"][i], raw["balloons"]["v"][i]))}
    L.append("COUPLING                                VS u     v      T       VSx      vertical-corr error   cross-variable corr error")
    for s in names:
        t = tab[s].mean()
        L.append(f"  {s:<36}" + "".join(f"{t['vs_' + q]:<7.3f}" for q in VARS) + f" {t['vsx']:<8.4f} {pooled['vertical-corr error'](s, every):<21.3f} {pooled['cross-variable corr error'](s, every):.3f}")
    L.append("SHAPE                                   shear p50 ratio per band      shear p99 ratio per band      Ri<1 share per band           co-extremes            depth-dev u v T      hydrostatic gap %")
    sb = np.concatenate(shear["balloons"])
    for s in ["balloons"] + names:
        sh = np.concatenate(shear[s])
        with np.errstate(all="ignore"):
            r50 = [np.nanpercentile(sh[:, i], 50) / np.nanpercentile(sb[:, i], 50) for i in MIDB]
            r99 = [np.nanpercentile(sh[:, i], 99) / np.nanpercentile(sb[:, i], 99) for i in MIDB]
        co = boot(lambda i, s=s: coext(raw[s]["u"][i].reshape(-1, K.NH), raw[s]["v"][i].reshape(-1, K.NH)), days, a.boot)
        dev = "   -     -     -   " if s == "balloons" else " ".join(f"{np.abs(h / max(h.sum(), 1) - 0.1).max():.3f}" for h in hist[s].values()) + " "
        L.append(f"  {s:<36}" + " ".join(f"{x:.2f}" for x in r50) + "           " + " ".join(f"{x:.2f}" for x in r99) + "           " + " ".join(f"{x:.3f}" for x in ri[s][:, 0] / np.maximum(ri[s][:, 1], 1))
                 + f"       {co[0]:.2f} [{co[1]:.2f}, {co[2]:.2f}]     {dev}   {100 * np.nanmedian(np.concatenate([np.ravel(x) for x in hyd[s]])):.3f}")
    for s in names[1:]:
        L.append(f"PAIRED {s} minus tool (day-block 95 % interval; below 0 = {s} better, above 0 = tool better, spans 0 = tie):")
        for col in ["crps_" + q for q in VARS] + ["vs_" + q for q in VARS] + ["vsx"]:
            d = (tab[s][col] - tab["tool"][col]).values
            ok = np.isfinite(d)
            mean, lo, hi = K.block_boot(d[ok], days[ok])
            verdict = f"{s} better" if hi < 0 else "tool better" if lo > 0 else "tie"
            L.append(f"  {col:<8} {mean:+.4f} [{lo:+.4f}, {hi:+.4f}]  ({100 * mean / tab['tool'][col].mean():+.1f} % of the tool's score)  {verdict}")
        L.append(f"POOLED {s} minus tool (day-bootstrap 95 % interval, same reading):")
        for name, fn in pooled.items():
            v, lo, hi = boot(lambda i, s=s, fn=fn: fn(s, i) - fn("tool", i), days, a.boot)
            verdict = f"{s} better" if hi < 0 else "tool better" if lo > 0 else "tie"
            L.append(f"  {name:<32} {v:+.4f} [{lo:+.4f}, {hi:+.4f}]  {verdict}")
    L.append("Notes: balloons 2024-25 are the development window; the tool is balloon-corrected at these two stations and gaussfull is fitted on their 1991-2020 balloons, "
             "so neither is a blind test. gaussfull is NOT Earth-GRAM. Depth-dev noise is about 0.03 at 600 cases. Co-extremes rest on about 5 % of the cases, so the balloon value itself is uncertain (its bracket). The 0-1 km balloon shear tail of 2024-25 is inflated by the 2023 sonde change (IL-194).")
    K.report("b9_gram_compare", L)


def _selfcheck():
    import io
    import tempfile
    rng = np.random.default_rng(0)
    e, y = rng.standard_normal((300, 3)), np.array([0.0, 1.0, np.nan])
    c = crps_cols(e, y)
    assert abs(c[0] - K.crps1(e[:, 0], 0.0)) < 1e-12 and abs(c[1] - K.crps1(e[:, 1], 1.0)) < 1e-12 and np.isnan(c[2])
    good, bad = 0.0, 0.0                                      # profiles that move together: the ensemble with the right link must beat the one without
    for _ in range(200):
        z = rng.standard_normal((201, 1)) + 0.1 * rng.standard_normal((201, 12))
        shuf = np.stack([rng.permutation(z[1:, k]) for k in range(12)], 1)          # same values per height, link between heights broken
        good, bad = good + vs_profile(z[1:], z[0]), bad + vs_profile(shuf, z[0])
        gx, bx = vs_cross(z[1:, :4, None], z[0, :4, None]), vs_cross(shuf[:, :4, None], z[0, :4, None])
        assert np.isfinite(gx) and np.isfinite(bx)
    assert good < 0.5 * bad, (good, bad)
    T = 288.0 - 0.0065 * K.H
    p = 1e5 * (T / 288.0) ** (G / (RD * 0.0065))
    assert np.nanmax(hydro_gap(T, p)) < 2e-4                 # a hydrostatic profile has no gap
    assert np.nanmedian(hydro_gap(T, p * (1 + 0.01 * np.arange(K.NH) / K.NH))) > 1e-4
    u = rng.standard_normal((20000, K.NH))
    ui = np.zeros((20000, K.NH))
    ui[:, 0], ui[:, J1] = u[:, 0], u[:, 0] + u[:, 1]         # shear = a number independent of the 10 m wind: 0.05
    assert abs(coext(ui, 0 * ui) - 0.05) < 0.02
    u2 = np.zeros((20000, K.NH))
    u2[:, 0], u2[:, J1] = u[:, 0], 3 * u[:, 0]               # shear = 2 x the 10 m wind: always together
    assert coext(np.abs(u2), 0 * u2) > 0.99
    base = {q: rng.standard_normal((400, K.NH)).cumsum(1) for q in (*VARS, "lnp")}
    assert vert_err(base, base) == 0.0 and cross_err(base, base) == 0.0
    noise = {q: rng.standard_normal((400, K.NH)) for q in base}
    assert vert_err(noise, base) > 0.3
    bk = bank_members(K.EPZ, 1, 0, 50, np.random.default_rng(0))     # 50 distinct complete real profiles, p in Pa
    assert bk["u"].shape == (50, K.NH) and np.isfinite(bk["p"]).all() and len({r.tobytes() for r in bk["T"]}) == 50 and 3e3 < np.median(bk["p"]) < 1.1e5
    v0, lo, hi = boot(lambda i: float(np.mean(i)), np.repeat(np.arange(50), 2), 50)
    assert lo < v0 < hi
    z = np.array([0.0, 5.0, 20000.0])                         # long table -> npz: linear in height, log in pressure
    tbl = pd.DataFrame([dict(case="X|2024-01-01T00", member=k, height_m=h, u=h / 1000.0, v=-1.0, T=280.0, p=9e4 * np.exp(-h / 8000.0)) for k in (0, 1) for h in z])
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "x.npz")
        assert csv_to_npz(io.StringIO(tbl.to_csv(index=False)), out) == (1, 2)
        idx, arr = load_external(out)
    assert idx == {"X|2024-01-01T00": 0} and np.allclose(arr["u"][0, 0], K.H / 1000.0, atol=1e-4) and np.allclose(arr["p"][0, 1], 9e4 * np.exp(-K.H / 8000.0), rtol=1e-4)


_selfcheck()
if __name__ == "__main__":
    main()
