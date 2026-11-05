"""IL-73: train and evaluate mode F (HRES forecast -> distribution of the 44-height profile). Train starts 2016-2019 (2020 early-stopping validation), range map 2021,
TEST 2022 (the archive ends 2023-01, so 2024-25 is not available). Needs data/modeF/<year>.npz from scripts/il6_build.py.

    PYTHONPATH=. python scripts/il6_modeF.py [--steps 3000] [--device cpu] [--retrain]

Methods per lead (1, 3, 5, 7 days): raw HRES profile (one value), HRES + empirical error pool of the same lead, residual network (raw), network + range map,
and a short-record climatology (2016-2020 truth rows of the same season and altitude). Reports CRPS, skill vs that climatology, MAE of the median, 99 % coverage,
PIT distance, per lead and variable x band.
"""
import argparse
import os

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.forecast import modeF as F
from tempest.forecast import modeP as P
from tempest.generator.sample import Sampler
from tempest.generator.train import train
from tempest.scoring import metrics_ext as M
from tempest.scoring.score import coverage90, crps_ensemble

ap = argparse.ArgumentParser()
ap.add_argument("--steps", type=int, default=3000)
ap.add_argument("--width", type=int, default=256)
ap.add_argument("--depth", type=int, default=3)
ap.add_argument("--members", type=int, default=2)
ap.add_argument("--device", default="cpu")
ap.add_argument("--m", type=int, default=199)
ap.add_argument("--rows", type=int, default=8000)
ap.add_argument("--out", default="models/modeF.pt")
ap.add_argument("--retrain", action="store_true")
ap.add_argument("--wd", type=float, default=1e-4)
ap.add_argument("--lr", type=float, default=1e-3)
ap.add_argument("--coarse", type=int, default=1, help="use every k-th height of the forecast profile as network input")
ap.add_argument("--noise-dim", type=int, default=16)
a = ap.parse_args()
rng = np.random.default_rng(0)
torch.manual_seed(0)
yrs = {y: dict(np.load(f"data/modeF/{y}.npz")) for y in range(2016, 2023)}
cat = lambda ys: {k: np.concatenate([yrs[y][k] for y in ys]) for k in yrs[2016]}
tr, cal, te = cat(range(2016, 2021)), cat([2021]), cat([2022])
def sub(d, n):
    """random subset of rows; ONE index for all arrays (drawing a new index per array once misaligned forecast and truth)"""
    i = np.sort(rng.choice(len(d['obs']), min(n, len(d['obs'])), replace=False))
    return {k: v[i] for k, v in d.items()}

cal, te = sub(cal, a.rows), sub(te, a.rows)
print(f"rows: train {len(tr['obs']):,}  range map {len(cal['obs']):,}  test {len(te['obs']):,}", flush=True)
if a.retrain or not os.path.exists(a.out):
    cfg = dict(width=a.width, depth=a.depth, noise_dim=a.noise_dim, m=4, batch=1024, steps=a.steps, eval_every=125, patience=6, val_years=1, lr=a.lr, weight_decay=a.wd, es_weight=0.1,
               step_weight=0.0, linear_features=[])
    train(F.cond_matrix(tr, a.coarse), F.residual(tr), tr["year"], cfg, out=a.out, device=a.device, meta=dict(cond_names=F.COND_NAMES), members=a.members)
net = Sampler(torch.load(a.out, map_location="cpu", weights_only=True), device=a.device)
m = a.m


def draw_net(d):
    c = F.cond_matrix(d, a.coarse)
    out = np.empty((len(c), m, F.D), np.float32)
    for i in range(0, len(c), 500):
        out[i:i + 500] = net(np.repeat(c[i:i + 500], m, 0)).reshape(len(c[i:i + 500]), m, -1)
    return F.to_physical(d["hres"].reshape(len(c), -1), out)


# alignment guard: forecast error must grow with lead time, otherwise forecast and truth are not the same cases
_e = np.abs(te["obs"] - te["hres"]).mean((1, 2))
_m = [_e[te["lead_days"] == L].mean() for L in (1, 7)]
assert _m[0] < _m[1], f"raw forecast error does not grow with lead ({_m}): arrays misaligned?"
truth_cal, truth = cal["obs"].reshape(len(cal["obs"]), -1), te["obs"].reshape(len(te["obs"]), -1)
table = P.fit_calibration(draw_net(cal), truth_cal, rng)
np.savez(a.out.rsplit(".", 1)[0] + ".calib.npz", **table)
x_net = draw_net(te)
x_cal = spread.apply(table, x_net, clip=False)
hres = te["hres"].reshape(len(truth), -1)
res_tr = (tr["obs"] - tr["hres"]).reshape(len(tr["obs"]), -1)
pool = np.empty((len(truth), m, F.D), np.float32)
for i in range(len(truth)):
    ok = np.flatnonzero(tr["lead_days"] == te["lead_days"][i])
    pool[i] = hres[i] + res_tr[rng.choice(ok, m)]
x_pool = F.to_physical(hres, pool - hres[:, None])
# linear (ridge) per lead + error pool of its own residuals
lin = np.empty((len(truth), m, F.D), np.float32)
h_tr = tr["hres"].reshape(len(tr["obs"]), -1)
for L in (1, 3, 5, 7):
    ktr, kte = tr["lead_days"] == L, te["lead_days"] == L
    mu, sd = h_tr[ktr].mean(0), h_tr[ktr].std(0) + 1e-6
    Z = np.concatenate([(h_tr[ktr] - mu) / sd, np.ones((ktr.sum(), 1))], 1)
    W = np.linalg.solve(Z.T @ Z + 200.0 * np.eye(Z.shape[1]), Z.T @ tr["obs"].reshape(len(tr["obs"]), -1)[ktr])
    fit_tr = Z @ W
    res_L = tr["obs"].reshape(len(tr["obs"]), -1)[ktr] - fit_tr
    Zt = np.concatenate([(hres[kte] - mu) / sd, np.ones((kte.sum(), 1))], 1)
    pred = Zt @ W
    idxs = np.flatnonzero(kte)
    for j, i in enumerate(idxs):
        lin[i] = pred[j] + res_L[rng.choice(len(res_L), m)]
lin = F.to_physical(np.zeros((len(truth), F.D), np.float32), lin)
# Schaake shuffle (IL-82): keep the network's marginals per column, take the dependence (ranks across the draws, by height and variable) from real forecast-error profiles
res_draw = x_pool - hres[:, None]                                    # real error profiles of the same lead (clip effects of RH are negligible here)
ranks = np.argsort(np.argsort(res_draw, axis=1), axis=1)
x_shuf = np.take_along_axis(np.sort(x_cal, axis=1), ranks, axis=1)
clim = np.empty_like(x_pool)
tro = tr["obs"].reshape(len(tr["obs"]), -1)
for i in range(len(truth)):
    dd = np.abs(((tr["doy"] - te["doy"][i] + 183) % 366) - 183)
    ok = np.flatnonzero((dd <= 20) & (np.abs(tr["z_sfc"] - te["z_sfc"][i]) < 250))
    clim[i] = tro[rng.choice(ok if len(ok) > 30 else np.arange(len(tro)), m)]
methods = {"climatology (2016-20 pool)": clim, "raw HRES profile": np.repeat(hres[:, None], 2, 1), "HRES + error pool": x_pool, "ridge + error pool": lin, "network + range map + Schaake shuffle": x_shuf, "network (raw)": x_net, "network + range map": x_cal}
bands = P.names()
masks = np.stack([s for _, _, s in bands], 1).astype(float)
masks /= masks.sum(0)
rows = []
for name, x in methods.items():
    crps = crps_ensemble(x, truth) @ masks
    mae = np.abs(np.median(x, 1) - truth) @ masks
    cov = (coverage90(x, truth, 0.99).astype(float) @ masks) if x.shape[1] > 2 else np.full((len(truth), len(bands)), np.nan)
    tv = M.pit_tv(M.pit_values(x, truth, rng)) if x.shape[1] > 2 else np.full(truth.shape[1], np.nan)
    for L in (1, 3, 5, 7):
        k = te["lead_days"] == L
        for b, (v, band, sel) in enumerate(bands):
            rows.append(dict(method=name, lead=L, var=v, band=band, crps=crps[k, b].mean(), mae=mae[k, b].mean(), cov99=cov[k, b].mean(), pit_tv=np.nan))
t = pd.DataFrame(rows)
t.to_csv(a.out.rsplit(".", 1)[0] + "_eval.csv", index=False)
pv = t.groupby(["method", "lead"])[["crps", "mae"]].mean().unstack("lead")
base = pv.loc["climatology (2016-20 pool)", "crps"]
print("mean CRPS over 16 variable x band cells, by lead (days)")
print(pv["crps"].round(3).to_string())
print("CRPS skill vs the short-record climatology")
print((1 - pv["crps"] / base).round(3).to_string())
print("MAE of the median")
print(pv["mae"].round(3).to_string())
cv = t[t.method.isin(["HRES + error pool", "ridge + error pool", "network (raw)", "network + range map"])].groupby(["method", "lead"]).cov99.apply(lambda c: (c - 0.99).abs().mean()).unstack("lead")
print("mean |cov99 - 0.99|")
print(cv.round(4).to_string())
print("skill vs climatology by variable (network + range map), lead 1 / 3 / 5 / 7")
sk = t[t.method == "network + range map"].groupby(["var", "lead"]).crps.mean().unstack("lead") / t[t.method.str.startswith("climatology")].groupby(["var", "lead"]).crps.mean().unstack("lead")
print((1 - sk).round(3).to_string())

# ---- shape metrics (MAIN TARGET) per lead for the probabilistic methods
try:
    from tempest.profiles.to_heights import PROFILE as _PROF
    levels = np.array([0.1, 0.25, 0.5, 0.75, 0.8, 0.9, 0.95, 0.99])
    srows = []
    for name in ("network + range map", "network + range map + Schaake shuffle", "ridge + error pool", "HRES + error pool"):
        x = methods[name]
        for L in (1, 3, 5, 7):
            k = te["lead_days"] == L
            xs, ys = x[k], truth[k]
            pit = M.pit_values(xs, ys, rng)
            tv = M.pit_tv(pit).mean()
            floor = M.pit_tv(M.pit_values(xs[:, 1:], xs[:, 0], rng)).mean()      # same statistic for a perfectly calibrated forecast (a member as pseudo-truth): the noise floor of this test set
            cov = np.abs(M.coverage_levels(pit) - levels[:, None]).mean()
            vc = [M.vertical_corr_error(xs, ys, np.arange(i * F.NH, (i + 1) * F.NH), rng=rng) for i in range(len(_PROF))]
            mom = M.standardized_moments(xs, ys)
            srows.append(dict(method=name, lead=L, pit_tv=tv, pit_floor=floor, cov_level_err=cov, vcorr_u=vc[0], vcorr_v=vc[1], vcorr_T=vc[2], vcorr_RH=vc[3],
                              skew_diff=np.abs(mom[:, 0] - mom[:, 1]).mean(), kurt_diff=np.abs(mom[:, 2] - mom[:, 3]).mean()))
    st = pd.DataFrame(srows)
    st.to_csv(a.out.rsplit(".", 1)[0] + "_shape.csv", index=False)
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print("shape metrics on the test rows (goals: PIT distance <= 0.02, level error <= 0.008, vertical corr error <= 0.05, skew <= 0.15, kurt <= 0.4)")
        print(st.to_string(index=False))
except Exception as e:  # noqa: BLE001
    print("shape block failed:", repr(e))
