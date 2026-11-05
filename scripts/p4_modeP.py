"""Mode P experiment (PHASE4_FORECAST.md 4.4): train the residual network, calibrate on 2021-23, score on the development years.

    PYTHONPATH=. python scripts/p4_modeP.py [--steps 3000] [--width 256] [--depth 3] [--device cpu]

Truth: IGRA 00Z soundings. Train: 1991-2020 (00Z and 12Z; the last 3 years are the early-stopping validation), range map: 2021-23 00Z,
test: 2024-25 00Z (development years). Methods compared per variable x height band (median error, CRPS, 99 % coverage, day-block 95 %
intervals): raw ERA5 (one value), ERA5 + empirical error pool of the same station/season, the existing station correction (a + b ERA5 +
leftover profile), the new residual network, and the climate generator E12 (median error from its sonde score file).
"""
import argparse
import os

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread, station
from tempest.forecast import modeP as P
from tempest.forecast.modeP import D
from tempest.generator.sample import Sampler
from tempest.generator.train import train
from tempest.profiles.to_heights import PROFILE
from tempest.scoring.score import coverage90, crps_ensemble


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--map", default="models/station_map_mix.npz")
    ap.add_argument("--out", default="models/modeP.pt")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--members", type=int, default=2)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--retrain", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    d = P.load_pairs(a.profiles, a.igra)
    yr, hr = d["time"].year.to_numpy(), d["time"].hour.to_numpy()
    sel = lambda m: {k: (v[m] if not isinstance(v, pd.DatetimeIndex) else v[m]) for k, v in d.items()}
    tr, cal, te = sel(yr <= 2020), sel((yr >= 2021) & (yr <= 2023) & (hr == 0)), sel((yr >= 2024) & (hr == 0))
    print(f"soundings: train {len(tr['era']):,}  range map {len(cal['era']):,}  test {len(te['era']):,}", flush=True)
    if a.retrain or not os.path.exists(a.out):
        cfg = dict(width=a.width, depth=a.depth, noise_dim=16, m=4, batch=512, steps=a.steps, eval_every=250, patience=10, val_years=3,
                   lr=1e-3, es_weight=0.1, step_weight=0.0, linear_features=[])
        train(P.cond_matrix(tr), P.residual(tr), tr["time"].year.to_numpy(), cfg, out=a.out, device=a.device, meta=dict(cond_names=P.COND_NAMES), members=a.members)
    net = Sampler(torch.load(a.out, map_location="cpu", weights_only=True), device=a.device)
    m = a.m

    def draw_net(dd):
        c = P.cond_matrix(dd)
        res = net(np.repeat(c, m, 0)).reshape(len(c), m, -1)
        return P.to_physical(dd["era"].reshape(len(c), -1), res)
    tmap = station.load(a.map)

    def draw_station(dd):
        g_ = station.group_id(dd["station"], dd["time"].month, np.zeros(len(dd["era"]), int))
        out_ = np.empty((len(dd["era"]), m, D), np.float32)
        for j in range(m):
            out_[:, j] = station.apply(tmap, dd["era"], g_, np.random.default_rng(j)).reshape(len(dd["era"]), -1)
        return out_
    cal_truth = cal["obs"].reshape(len(cal["era"]), -1)
    table = P.fit_calibration(draw_net(cal), cal_truth, rng)
    np.savez(a.out.rsplit(".", 1)[0] + ".calib.npz", **table)
    truth = te["obs"].reshape(len(te["era"]), -1)
    era = te["era"].reshape(len(te["era"]), -1)
    methods = {"raw ERA5": np.repeat(era[:, None], 2, 1)}
    # ERA5 + empirical error pool of the same station and season (fit years)
    season = lambda dd: station.season(dd["time"].month)
    res_pool = (tr["obs"] - tr["era"]).reshape(len(tr["era"]), -1)
    out = np.empty((len(era), m, era.shape[1]), np.float32)
    for i in range(len(era)):
        ok = np.flatnonzero((tr["station"] == te["station"][i]) & (season(tr) == season(te)[i]) & (tr["hour12"] == 0))
        out[i] = era[i] + res_pool[rng.choice(ok, m)]
    methods["ERA5 + error pool"] = P.to_physical(era, out - era[:, None])
    # existing station correction
    methods["station correction (a+bE+leftover)"] = draw_station(te)
    methods["residual network (raw)"] = draw_net(te)
    net_cal = spread.apply(table, draw_net(te), clip=False)
    methods["residual network + range map"] = net_cal
    # hybrid: per variable x band, the method with the lower CRPS on the 2021-23 range-map soundings (never the test years)
    c_net = crps_ensemble(spread.apply(table, draw_net(cal), clip=False), cal_truth).mean(0)
    c_sta = crps_ensemble(draw_station(cal), cal_truth).mean(0)
    use_net = np.zeros(D, bool)
    for v, b, sel_ in P.names():
        use_net[sel_] = c_net[sel_].mean() <= c_sta[sel_].mean()
        print(f"hybrid choice {v} {b}: {'network' if use_net[sel_][0] else 'station correction'} (CRPS on 2021-23: network {c_net[sel_].mean():.3f}, station {c_sta[sel_].mean():.3f})")
    np.save(a.out.rsplit(".", 1)[0] + ".hybrid_use_network.npy", use_net)
    methods["hybrid (chosen on 2021-23)"] = np.where(use_net[None, None, :], net_cal, methods["station correction (a+bE+leftover)"])
    day = te["time"].year.to_numpy().astype(np.int64) * 1000 + te["time"].dayofyear.to_numpy()
    _, inv = np.unique(day, return_inverse=True)
    nd = inv.max() + 1
    boot = np.vstack([np.ones(nd), np.random.default_rng(0).multinomial(nd, np.full(nd, 1 / nd), 300)])
    cnt = np.bincount(inv, minlength=nd)
    dm = lambda v: (boot @ np.stack([np.bincount(inv, v[:, g_], nd) for g_ in range(v.shape[1])], 1)) / (boot @ cnt)[:, None]
    bands = P.names()
    masks = np.stack([s for _, _, s in bands], 1).astype(float)
    masks /= masks.sum(0)
    rows = []
    for name, x in methods.items():
        mae = np.abs(np.median(x, 1) - truth) @ masks
        crps = crps_ensemble(x, truth) @ masks
        cov = (coverage90(x, truth, 0.99).astype(float) @ masks) if x.shape[1] > 2 else np.full((len(truth), len(bands)), np.nan)
        b_mae, b_crps, b_cov = dm(mae), dm(crps), dm(cov)
        for k, (v, b, _) in enumerate(bands):
            f = lambda q: f"{q[0, k]:.3f} [{np.percentile(q[1:, k], 2.5):.3f}, {np.percentile(q[1:, k], 97.5):.3f}]"
            rows.append(dict(method=name, var=v, band=b, mae=f(b_mae), crps=f(b_crps), cov99=(f(b_cov) if x.shape[1] > 2 else ""),
                             mae0=b_mae[0, k], crps0=b_crps[0, k], cov0=b_cov[0, k]))
    t = pd.DataFrame(rows)
    t.to_csv(a.out.rsplit(".", 1)[0] + "_eval.csv", index=False)
    s = t.groupby("method")[["mae0", "crps0"]].mean()
    s["mean |cov99-0.99|"] = t.groupby("method").cov0.apply(lambda c: (c - 0.99).abs().mean())
    with pd.option_context("display.width", 250, "display.float_format", "{:.4f}".format):
        print(s.to_string())
        for v in PROFILE:
            print(f"\n{v}: MAE of the median / CRPS by band")
            print(t[t["var"] == v].pivot(index="band", columns="method", values="mae0").round(3).to_string())
            print(t[t["var"] == v].pivot(index="band", columns="method", values="crps0").round(3).to_string())


if __name__ == "__main__":
    main()
