"""New_Plan 28.10 X4-R dev-year probe (no retrain, no scoring): is the base network's Denver mean error a stable, harmonic
climatology offset that a table fitted on years <= 2020 removes on 2021-23, while the same table stays near zero in NM/TX?
Per point: harmonic fit (fit_anom_table basis) of the observed targets and of the network's ensemble mean on the same rows (<= 2020);
X4-R offset = the difference, coefficients soft-thresholded by k x their NM/TX rms. Reported on 2021-23 rows (never fitted):
mean-error MSE of the network mean in ts units per variable group, before / after the offset, and the share left by constant-only.

    python scripts/x4r_probe.py models/s25/base_s0.pt [--rows 60000] [--k 2]
"""
import argparse

import numpy as np
import torch

from tempest.generator.model import ANOM_COLS, anom_basis, fit_anom_table
from tempest.generator.sample import Sampler, standard_pressure
from tempest.generator.train import _load

DEN, NMTX = "data/train/denver_full_fill_dpd.npz", "data/train/pilot80_l21_all24_dpd.npz"
GROUPS = ["u_", "v_", "T_", "RH_", "t2m", "sp", "rh2m"]


def rows(d, lo, hi, n, seed):
    yr = np.asarray(d["year"])
    i = np.flatnonzero((yr >= lo) & (yr <= hi))
    return np.sort(np.random.default_rng(seed).choice(i, min(n, len(i)), replace=False))


def net_mean(s, cond, k, sp):
    out = sum(np.concatenate([s(cond[j:j + 20000]) for j in range(0, len(cond), 20000)]).astype(np.float64) for _ in range(k)) / k
    if sp is not None:
        out[:, sp[0]] -= standard_pressure(cond[:, sp[1]])
    return out


def tgt(d, idx, sp):
    t = np.array(d["target"][idx], np.float64)
    if sp is not None:
        t[:, sp[0]] -= standard_pressure(np.asarray(d["cond"][idx, sp[1]], np.float64))
    return t


def fit(c6, y, floor):
    keys, cmu, _ = fit_anom_table(c6, y, floor)
    return keys, cmu


def eval_mu(keys, cmu, c6):
    p = np.argmin(((np.round(c6[:, None, :2], 3) - keys[None]) ** 2).sum(-1), 1)
    X = anom_basis(c6[:, 2], c6[:, 3], c6[:, 4], c6[:, 5], np)
    return np.einsum("bk,bkd->bd", X, cmu[p])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"), ap.add_argument("--rows", type=int, default=60000), ap.add_argument("--k", type=float, nargs="+", default=[2.0])
    ap.add_argument("--draws", type=int, default=8)
    a = ap.parse_args()
    torch.manual_seed(0)
    ck = torch.load(a.model, map_location="cpu", weights_only=True)
    k0 = ck.get("members", [ck])[0]
    sp, ts = k0.get("sp_offset"), k0["norm"]["ts"].numpy().astype(np.float64)
    tn = [str(x) for x in np.asarray(_load(DEN)["target_names"])]
    s = Sampler(ck)
    res = {}
    for tag, path in (("NMTX", NMTX), ("DEN", DEN)):
        d = _load(path)
        names = [str(x) for x in d["cond_names"]]
        ac = [names.index(c) for c in ANOM_COLS]
        tr, te = rows(d, 1991, 2020, a.rows, 0), rows(d, 2021, 2023, a.rows // 2, 1)
        ctr, cte = np.asarray(d["cond"][tr], np.float64), np.asarray(d["cond"][te], np.float64)
        ytr, yte = tgt(d, tr, sp), tgt(d, te, sp)
        ok = np.isfinite(ytr).all(1)
        mtr, mte = net_mean(s, ctr.astype(np.float32), a.draws, sp), net_mean(s, cte.astype(np.float32), a.draws, sp)
        keys, c_obs = fit(ctr[ok][:, ac], ytr[ok], 1e-3 * ts)
        _, c_net = fit(ctr[ok][:, ac], mtr[ok], 1e-3 * ts)
        res[tag] = dict(keys=keys, dc=c_obs - c_net, c6=cte[:, ac], yte=yte, mte=mte)
        print(f"{tag}: {len(keys)} points, fit rows {ok.sum()}, test rows {len(te)}", flush=True)
    rms = np.sqrt((res["NMTX"]["dc"] ** 2).mean(0))                 # (11, D) in-domain spread of each coefficient
    for tag, k in [(t, k) for k in a.k for t in ("NMTX", "DEN")]:
        r = res[tag]
        dc_soft = np.sign(r["dc"]) * np.maximum(np.abs(r["dc"]) - k * rms, 0)
        dc_const = r["dc"].copy(); dc_const[:, 1:] = 0
        ok = np.isfinite(r["yte"]).all(1)
        e0 = (r["yte"] - r["mte"])[ok] / ts
        print(f"\n{tag} 2021-23 mean-error MSE (ts units, per group): base | full offset | soft k={k} | constant only | frac coeffs kept")
        for name, dc in (("full", r["dc"]), ("soft", dc_soft), ("const", dc_const)):
            r[name] = e0 - eval_mu(r["keys"], dc, r["c6"][ok]) / ts
        kept = (np.abs(dc_soft) > 0).mean()
        for g in GROUPS:
            j = [i for i, t in enumerate(tn) if t.startswith(g)]
            m = lambda e: float((e[:, j] ** 2).mean())
            print(f"  {g:5s} {m(e0):8.4f} | {m(r['full']):8.4f} | {m(r['soft']):8.4f} | {m(r['const']):8.4f}")
        print(f"  all   {float((e0 ** 2).mean()):8.4f} | {float((r['full'] ** 2).mean()):8.4f} | {float((r['soft'] ** 2).mean()):8.4f} | "
              f"{float((r['const'] ** 2).mean()):8.4f} | kept {kept:.3f}")


def _selfcheck():
    rng = np.random.default_rng(0)
    c6 = np.c_[np.repeat([[35.0, -105.0]], 400, 0), np.sin(rng.uniform(0, 6.28, (400, 1))), np.cos(rng.uniform(0, 6.28, (400, 1))),
               np.sin(rng.uniform(0, 6.28, (400, 1))), np.cos(rng.uniform(0, 6.28, (400, 1)))]
    y = 3.0 + 0 * c6[:, :1]
    keys, cmu = fit(c6, y, np.array([1e-3]))
    assert np.allclose(eval_mu(keys, cmu, c6), 3.0, atol=1e-6)


_selfcheck()
if __name__ == "__main__":
    main()
