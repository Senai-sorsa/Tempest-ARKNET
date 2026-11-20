"""New_Plan 28.10 variant d, X4-R: attach a residual-referenced climatology offset to an unchanged base checkpoint (no retrain).
Per point (NM/TX training points and Denver points, years <= 2020): harmonic fit (fit_anom_table basis) of the observed targets minus the
same fit of the base network's ensemble mean on the same input rows; each coefficient soft-thresholded by k x its rms over the NM/TX
points (the in-domain spread = fit noise), so the offset is ~0 where the network is already right. Loaded as the X4 anom mean_only path:
model output z + (mu - tm) / ts with mu = offset + tm, i.e. the raw ensemble mean moves by the offset; spread untouched.

    python scripts/x4r_build.py models/s25/base_s0.pt models/s25/x4rs25_s0.pt [--k 2] [--rows 400000] [--draws 4]
"""
import argparse

import numpy as np
import torch

from tempest.generator.model import ANOM_COLS
from tempest.generator.sample import Sampler
from tempest.generator.train import _load
from x4r_probe import DEN, NMTX, fit, net_mean, rows, tgt


def offsets(ck, rows_n, draws):
    k0 = ck["members"][0]
    sp, ts = k0.get("sp_offset"), k0["norm"]["ts"].numpy().astype(np.float64)
    s = Sampler(ck)
    out = {}
    for tag, path in (("NMTX", NMTX), ("DEN", DEN)):
        d = _load(path)
        names = [str(x) for x in d["cond_names"]]
        assert names == list(k0["cond_names"]), f"{path} inputs differ from the checkpoint's"
        ac = [names.index(c) for c in ANOM_COLS]
        tr = rows(d, 1991, 2020, rows_n, 0)
        c = np.asarray(d["cond"][tr], np.float64)
        y = tgt(d, tr, sp)
        m = net_mean(s, c.astype(np.float32), draws, sp)
        ok = np.isfinite(y).all(1)
        keys, c_obs = fit(c[ok][:, ac], y[ok], 1e-3 * ts)
        _, c_net = fit(c[ok][:, ac], m[ok], 1e-3 * ts)
        out[tag] = (keys, c_obs - c_net)
        print(f"{tag}: {len(keys)} points from {int(ok.sum())} rows", flush=True)
    return out, [list(k0["cond_names"]).index(c) for c in ANOM_COLS]


def attach(ck, keys, dc, ac):
    for m in ck["members"]:
        tm, ts = m["norm"]["tm"].double().numpy(), m["norm"]["ts"].double().numpy()
        cmu = dc.copy()
        cmu[:, 0, :] += tm                                              # basis term 0 is the constant: mu - tm = offset
        m["model_kw"] = dict(anom=dict(cols=ac, mu=[float(m["norm"]["cm"][i]) for i in ac], sd=[float(m["norm"]["cs"][i]) for i in ac],
                                       P=len(keys), tm=[float(x) for x in tm], ts=[float(x) for x in ts], mean_only=True))
        st = m["state"]
        for n, v in (("mu", m["model_kw"]["anom"]["mu"]), ("sd", m["model_kw"]["anom"]["sd"]), ("tm", tm), ("ts", ts)):
            st[f"anom_{n}"] = torch.tensor(np.asarray(v), dtype=torch.float32)
        st["anom_keys"] = torch.as_tensor(keys, dtype=torch.float32)
        st["anom_cmu"] = torch.as_tensor(cmu, dtype=torch.float32)
        st["anom_clv"] = torch.zeros_like(st["anom_cmu"])
    return ck


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"), ap.add_argument("out")
    ap.add_argument("--k", type=float, default=2.0), ap.add_argument("--rows", type=int, default=400000), ap.add_argument("--draws", type=int, default=4)
    a = ap.parse_args()
    torch.manual_seed(0)
    load = lambda: torch.load(a.base, map_location="cpu", weights_only=True)
    ck = load()
    assert "members" in ck and not any("model_kw" in m and "anom" in m["model_kw"] for m in ck["members"]), "expects a plain base ensemble"
    off, ac = offsets(ck, a.rows, a.draws)
    rms = np.sqrt((off["NMTX"][1] ** 2).mean(0))
    keys = np.concatenate([off["NMTX"][0], off["DEN"][0]])
    dc = np.concatenate([off["NMTX"][1], off["DEN"][1]])
    soft = np.sign(dc) * np.maximum(np.abs(dc) - a.k * rms, 0)
    n_in = len(off["NMTX"][0])
    print(f"k {a.k}: coefficients kept NM/TX {(soft[:n_in] != 0).mean():.3f}, Denver {(soft[n_in:] != 0).mean():.3f}")
    # self-check: a zero table must reproduce the base samples exactly (same noise), so only the offset changes anything
    probe = np.asarray(_load(NMTX)["cond"][:4000], np.float32)
    torch.manual_seed(1); y0 = Sampler(load())(probe)
    torch.manual_seed(1); y1 = Sampler(attach(load(), keys, np.zeros_like(dc), ac))(probe)
    assert np.allclose(y0, y1, rtol=1e-5, atol=1e-4 * float(np.abs(y0).max())), f"zero-table X4-R differs from the base by {np.abs(y0 - y1).max()}"
    torch.save(attach(ck, keys, soft, ac), a.out)
    print(f"{a.out}: X4-R table at {len(keys)} points (k {a.k}), zero-table check ok")


if __name__ == "__main__":
    main()
