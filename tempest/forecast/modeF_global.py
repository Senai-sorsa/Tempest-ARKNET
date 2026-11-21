"""G3 global-style Mode F (GLOBAL_PLAN G3): one forecast corrector for every place and lead.

    python -m tempest.forecast.modeF_global rows  --out data/train/modeF_global_na.npz --box 15 75 -170 -50 [--points 300]
    python -m tempest.forecast.modeF_global train --rows data/train/modeF_global_na.npz --out results/G3/modeF_global.pt
    python -m tempest.forecast.modeF_global score --rows data/train/modeF_global_na.npz --model results/G3/modeF_global.pt \
        --out results/G3/modeF_global_score.csv [--box 31 37 -109 -101]

Rows: WeatherBench2 HRES (data/raw/wb2_hres_global, 2016-2022, levels flipped to the store's 1000 -> 50 hPa order, q -> RH)
at store points whose valid time is the store's hour of that day, against the ERA5 store profile (truth). Each HRES
record is one start / lead; the forecast profile is built with tempest.geo.global_store.profiles (100 m wind = 1.4 x
10 m wind, 2 m dew point from the RH of the lowest level above ground, as tempest.forecast.modeF DEFAULT_BL).
Network: input = DeepSets summary of the M forecast members (member mean, member std, log M; HRES has M = 1 so std = 0
and log M = 0, IFS-ENS M = 51 uses the same weights), the lead (hours / 240), season, solar hour, sin(lat), surface
height, and the climatology prior (tempest.geo.clim_global mean and spread at the place and time, optional).
Output: a Gaussian per column (mean shift of the residual ERA5 - forecast, log spread), trained on the closed-form
Gaussian CRPS. Years: train 2016-2020, validation 2021, score 2022 (G stages never read 2026).
"""
import argparse
import os

import numpy as np

from tempest.profiles.to_heights import HEIGHTS, PROFILE

D = len(PROFILE) * len(HEIGHTS)
TRAIN, VAL, TEST = (2016, 2020), (2021, 2021), (2022, 2022)
RATIO_100M = 1.4                                    # tempest.forecast.modeF DEFAULT_BL: neutral log law


def hres_month(h, pts):
    """Decoded HRES month (tempest.geo.global_store.hres) -> store-like dict: levels 1000 -> 50 hPa, z in m2/s2, RH (%)."""
    from tempest.geo.global_store import q_to_rh
    lev = np.asarray(h["level"], float)
    o = np.argsort(-lev)                                                              # HRES files run 50 -> 1000 hPa
    m = {k: np.asarray(h[k])[:, o] for k in ("u", "v", "t", "z")}
    m["r"] = q_to_rh(np.asarray(h["q"])[:, o], m["t"], lev[o][None, :, None])
    m["level"] = lev[o]
    for k in ("u10", "v10", "t2m", "sp"):
        m[k] = np.asarray(h[k])
    m["u100"], m["v100"] = RATIO_100M * m["u10"], RATIO_100M * m["v10"]
    # 2 m dew point: the dew point depression of the lowest level above ground, put on t2m (DEFAULT_BL dpd_a 0, b 1)
    from tempest.forecast.modeF import _td_from_rh
    from tempest.geo.statics import statics
    oro = statics(pts["lat"], pts["lon"])["oro_m"]
    agl = m["z"] / 9.80665 - oro[None, None, :]
    low = np.where(agl > 0, agl, np.inf).argmin(1)                                   # (n, P)
    tl = np.take_along_axis(m["t"], low[:, None], 1)[:, 0]
    rl = np.take_along_axis(m["r"], low[:, None], 1)[:, 0]
    m["d2m"] = m["t2m"] - np.clip(tl - _td_from_rh(tl, rl), 0.0, 60.0)
    return m, oro


def rows(first=2016, last=2022, box=None, points=300, seed=0, hres_store=None, store=None, log=print):
    """-> dict(fc (n, D), obs (n, D), lead_h, valid, lat, lon, oro, year) for random store points per matched record."""
    from tempest.geo import global_store as gs
    from tempest.geo import points as gp
    hres_store, store = hres_store or gs.HRES, store or gs.STORE
    pts = gs.points(store)
    with np.load(os.path.join(hres_store, "points.npz")) as d:
        if not (np.allclose(d["lat"], pts["lat"]) and np.allclose(d["lon"], pts["lon"])):
            raise ValueError("HRES and ERA5 global stores hold different point sets")
    idx = gp.select(pts, tuple(box) if box else None)
    rng = np.random.default_rng(seed)
    out, cache = [], {}
    for f in sorted(os.listdir(hres_store)):
        if len(f) != 10 or not f[:6].isdigit() or not first <= int(f[:4]) <= last:
            continue
        h = gs.hres(f[:6], hres_store)
        m, oro = hres_month(h, pts)
        for i, vt in enumerate(np.asarray(h["valid"], "datetime64[h]")):
            name = str(vt.astype("datetime64[M]"))
            if name not in cache:
                cache.clear()
                p = os.path.join(store, f"{name}.npz")
                cache[name] = gs.month(name, store) if os.path.exists(p) else None
            e = cache[name]
            if e is None:
                continue
            j = np.flatnonzero(np.asarray(e["valid_time"], "datetime64[h]") == vt)
            if not len(j):
                continue                                                              # the store holds another hour that day
            p = rng.choice(idx, min(points, len(idx)), replace=False)
            fc, _ = gs.profiles(m, pts, p, t=slice(i, i + 1), oro_m=oro[p])
            ob, _ = gs.profiles(e, pts, p, t=slice(j[0], j[0] + 1), oro_m=oro[p])
            out.append(dict(fc=np.concatenate([fc[v][0] for v in PROFILE], -1), obs=np.concatenate([ob[v][0] for v in PROFILE], -1),
                            lead_h=np.full(len(p), h["lead_h"][i], np.int16), valid=np.full(len(p), vt),
                            lat=pts["lat"][p], lon=pts["lon"][p], oro=oro[p]))
        log(f"{f[:6]}: {sum(len(q['lat']) for q in out):,} rows")
    if not out:
        raise FileNotFoundError(f"no HRES record in {hres_store} matches a store hour in {first}-{last}")
    r = {k: np.concatenate([q[k] for q in out]) for k in out[0]}
    ok = np.isfinite(r["fc"]).all(1) & np.isfinite(r["obs"]).all(1)
    r = {k: v[ok] for k, v in r.items()}
    r["year"] = r["valid"].astype("datetime64[Y]").astype(int) + 1970
    return r


def summary(members):
    """(n, M, F) forecast members -> (n, 2F + 1) DeepSets summary: member mean, member std, log M (M = 1 -> std 0)."""
    x = np.asarray(members, np.float32)
    return np.concatenate([x.mean(1), x.std(1), np.full((len(x), 1), np.log(x.shape[1]), np.float32)], 1)


def inputs(r, members=None, clim=None):
    """Network inputs. members (n, M, D) defaults to the single HRES forecast r["fc"]."""
    t = np.asarray(r["valid"], "datetime64[h]")
    doy = (t - t.astype("datetime64[Y]")).astype("timedelta64[D]").astype(float)
    sh = (t.astype(np.int64) % 24 + np.asarray(r["lon"], float) / 15.0) % 24
    a, b = 2 * np.pi * doy / 365.25, 2 * np.pi * sh / 24
    head = np.stack([np.asarray(r["lead_h"], float) / 240.0, np.sin(a), np.cos(a), np.sin(b), np.cos(b),
                     np.sin(np.radians(r["lat"])), np.asarray(r["oro"], float) / 1e3], 1)
    parts = [head, summary(r["fc"][:, None] if members is None else members)]
    if clim is not None:
        from tempest.geo import clim_global as cg
        mu, sd = cg.predict(clim, r["lat"], r["lon"], t)
        k = len(PROFILE) * len(HEIGHTS)                                              # the profile columns; t2m / sp / rh2m not used
        parts += [mu[:, :k], np.log(np.maximum(sd[:, :k], 1e-3))]
    return np.concatenate(parts, 1).astype(np.float32)


def crps_gauss(mu, sd, y):
    """Closed-form CRPS of N(mu, sd^2) at y (numpy or torch)."""
    if isinstance(mu, np.ndarray):
        from scipy.stats import norm
        z = (y - mu) / sd
        return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))
    import torch
    z = (y - mu) / sd
    n = torch.distributions.Normal(0.0, 1.0)
    return sd * (z * (2 * n.cdf(z) - 1) + 2 * torch.exp(n.log_prob(z)) - 1 / np.sqrt(np.pi))


def _net(n_in, width, depth):
    import torch.nn as nn
    layers, w = [], n_in
    for _ in range(depth):
        layers += [nn.Linear(w, width), nn.SiLU()]
        w = width
    return nn.Sequential(*layers, nn.Linear(w, 2 * D))


def train(r, out, clim=None, width=512, depth=3, epochs=30, lr=1e-3, batch=2048, device=None, seed=0, log=print):
    import torch
    torch.manual_seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    X, Y = inputs(r, clim=clim), (r["obs"] - r["fc"]).astype(np.float32)
    tr = (r["year"] >= TRAIN[0]) & (r["year"] <= TRAIN[1])
    va = (r["year"] >= VAL[0]) & (r["year"] <= VAL[1])
    if not tr.any() or not va.any():
        raise ValueError(f"need rows in the train years {TRAIN} and the validation years {VAL}")
    xm, xs = X[tr].mean(0), X[tr].std(0) + 1e-6
    ys = Y[tr].std(0) + 1e-6
    net = _net(X.shape[1], width, depth).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    t = lambda a: torch.as_tensor(a, device=device)
    Xt, Yt = t((X[tr] - xm) / xs), t(Y[tr] / ys)
    Xv, Yv = t((X[va] - xm) / xs), t(Y[va] / ys)
    best, state = np.inf, None
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xt), device=device)
        for i in range(0, len(Xt), batch):
            b = perm[i:i + batch]
            o = net(Xt[b])
            loss = crps_gauss(o[:, :D], torch.exp(o[:, D:].clamp(-7, 5)), Yt[b]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            o = torch.cat([net(Xv[i:i + 16384]) for i in range(0, len(Xv), 16384)])
            v = float(crps_gauss(o[:, :D], torch.exp(o[:, D:].clamp(-7, 5)), Yv).mean())
        log(f"epoch {ep}: train {float(loss.detach()):.4f} val {v:.4f}")
        if v < best:
            best, state = v, {k: x.detach().cpu().clone() for k, x in net.state_dict().items()}
    ck = dict(state=state, n_in=X.shape[1], width=width, depth=depth, xm=xm, xs=xs, ys=ys, val_crps=best,
              clim=bool(clim is not None), years=dict(train=TRAIN, val=VAL, test=TEST))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    torch.save(ck, out)
    return ck


def predict(ck, X):
    """-> mean, sd (n, D) of the residual ERA5 - forecast in physical units."""
    import torch
    net = _net(ck["n_in"], ck["width"], ck["depth"])
    net.load_state_dict(ck["state"])
    net.eval()
    with torch.no_grad():
        o = net(torch.as_tensor((X - ck["xm"]) / ck["xs"], dtype=torch.float32)).numpy()
    return o[:, :D] * ck["ys"], np.exp(np.clip(o[:, D:], -7, 5)) * ck["ys"]


def score(r, ck, clim=None, box=None, years=None):
    """CRPS per lead (days, rounded) and variable: raw forecast (a point = MAE) vs the corrected Gaussian."""
    import pandas as pd
    years = years or TEST
    k = (r["year"] >= years[0]) & (r["year"] <= years[1])
    if box is not None:
        la, lo = r["lat"], (r["lon"] + 180) % 360 - 180
        k &= (la >= box[0]) & (la <= box[1]) & (lo >= box[2]) & (lo <= box[3])
    if not k.any():
        raise ValueError("no rows to score")
    s = {q: v[k] for q, v in r.items()}
    mu, sd = predict(ck, inputs(s, clim=clim if ck.get("clim") else None))
    y = s["obs"] - s["fc"]
    c_raw, c_cor = np.abs(y), crps_gauss(mu, sd, y)
    lead_d = np.round(s["lead_h"] / 24.0).astype(int)
    out = []
    for L in np.unique(lead_d):
        j = lead_d == L
        for vi, v in enumerate(PROFILE):
            cols = slice(vi * len(HEIGHTS), (vi + 1) * len(HEIGHTS))
            out.append(dict(lead_days=int(L), var=v, n=int(j.sum()), crps_raw=float(c_raw[j, cols].mean()),
                            crps_cor=float(c_cor[j, cols].mean())))
    df = pd.DataFrame(out)
    df["skill"] = 1 - df["crps_cor"] / df["crps_raw"]
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("rows")
    a.add_argument("--out", required=True)
    a.add_argument("--box", type=float, nargs=4, metavar=("LAT0", "LAT1", "LON0", "LON1"))
    a.add_argument("--points", type=int, default=300, help="store points drawn per matched HRES record")
    a.add_argument("--first-year", type=int, default=2016)
    a.add_argument("--last-year", type=int, default=2022)
    a.add_argument("--seed", type=int, default=0)
    t = sp.add_parser("train")
    t.add_argument("--rows", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--clim", help="tempest.geo.clim_global table: climatology prior input")
    t.add_argument("--epochs", type=int, default=30)
    t.add_argument("--width", type=int, default=512)
    t.add_argument("--seed", type=int, default=0)
    s = sp.add_parser("score")
    s.add_argument("--rows", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--clim")
    s.add_argument("--box", type=float, nargs=4, metavar=("LAT0", "LAT1", "LON0", "LON1"))
    g = ap.parse_args()
    if g.cmd == "rows":
        if g.last_year > 2025:
            raise SystemExit("G stages never read 2026")
        r = rows(g.first_year, g.last_year, g.box, g.points, g.seed)
        os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
        with open(g.out, "wb") as fh:
            np.savez(fh, **r)
        print(f"wrote {g.out}: {len(r['lat']):,} rows", flush=True)
        return
    r = dict(np.load(g.rows))
    clim = None
    if g.clim:
        from tempest.geo import clim_global as cg
        clim = cg.load(g.clim)
    if g.cmd == "train":
        ck = train(r, g.out, clim, width=g.width, epochs=g.epochs, seed=g.seed)
        print(f"wrote {g.out}: best validation CRPS (standardised) {ck['val_crps']:.4f}", flush=True)
    else:
        import torch
        ck = torch.load(g.model, map_location="cpu", weights_only=False)
        df = score(r, ck, clim, g.box)
        os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
        df.to_csv(g.out, index=False)
        print(df.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
