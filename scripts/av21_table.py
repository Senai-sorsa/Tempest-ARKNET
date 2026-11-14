"""New_Plan 13 AV21: swap the anomaly climatology table of an anom_clim checkpoint (tempest/generator/model.py anom) for one fitted on
another dataset's rows of years <= --max-year (default 2020: the calibration 2021-23 and test 2024-25 years never enter). Same fit as
training (fit_anom_table on up to 1M rows, sp offset removed, floor 1e-3 ts); network weights and normalisation stay as trained.
Used for the Denver zero-shot: the network was trained on NM/TX, the climatology it standardises by is Denver's.

    python scripts/av21_table.py models/av21.pt data/train/denver_full_fill_dpd.npz models/av21_denfill.pt
"""
import argparse

import numpy as np
import torch

from tempest.generator.model import fit_anom_table
from tempest.generator.sample import standard_pressure
from tempest.generator.train import _load


def table(ck, data, max_year, rows=1_000_000, seed=0):
    k0 = ck.get("members", [ck])[0]
    a = k0["model_kw"]["anom"]
    names = [str(n) for n in data["cond_names"]]
    assert names == [str(n) for n in k0["cond_names"]], "dataset inputs differ from the checkpoint's"
    yr = np.asarray(data["year"])
    idx = np.flatnonzero(yr <= max_year)
    if len(idx) > rows:
        idx = np.sort(np.random.default_rng(seed).choice(idx, rows, replace=False))
    t = np.array(data["target"][idx], np.float64)
    if k0.get("sp_offset"):
        tc, cc = k0["sp_offset"]
        t[:, tc] -= standard_pressure(np.asarray(data["cond"][idx, cc], np.float64))
    ok = np.isfinite(t).all(1)
    assert ok.mean() > 0.95, f"only {ok.mean():.1%} of the rows are finite"
    c6 = np.asarray(data["cond"][idx][:, a["cols"]], np.float64)
    return fit_anom_table(c6[ok], t[ok], 1e-3 * np.asarray(a["ts"])), int(ok.sum())


def swap(ck, tab):
    keys, cmu, clv = tab
    for k in ck.get("members", [ck]):
        k["model_kw"]["anom"]["P"] = len(keys)
        k["state"]["anom_keys"] = torch.as_tensor(keys, dtype=torch.float32)
        k["state"]["anom_cmu"] = torch.as_tensor(cmu, dtype=torch.float32)
        k["state"]["anom_clv"] = torch.as_tensor(clv, dtype=torch.float32)
    return ck


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"), ap.add_argument("data"), ap.add_argument("out")
    ap.add_argument("--max-year", type=int, default=2020)
    a = ap.parse_args()
    ck = torch.load(a.model, map_location="cpu", weights_only=True)
    tab, n = table(ck, _load(a.data), a.max_year)
    torch.save(swap(ck, tab), a.out)
    print(f"{a.out}: table refitted on {n} rows <= {a.max_year} of {a.data}, {len(tab[0])} points")


def _selfcheck():
    ck = dict(members=[dict(model_kw=dict(anom=dict(P=3)), state={}) for _ in range(2)])
    swap(ck, (np.zeros((5, 2)), np.zeros((5, 11, 4)), np.zeros((5, 11, 4))))
    assert all(m["model_kw"]["anom"]["P"] == 5 and m["state"]["anom_cmu"].shape == (5, 11, 4) for m in ck["members"])


_selfcheck()
if __name__ == "__main__":
    main()
