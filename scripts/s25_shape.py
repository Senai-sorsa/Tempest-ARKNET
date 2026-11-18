"""New_Plan 25 extra shape metrics for one model and one stack, ERA5 truth, verdict years (default 2024-25).

    PYTHONPATH=. python scripts/s25_shape.py MODEL.pt CALIB.npz DATA.npz --out STEM [--shuffle --template-cell 8] [--shear-map F] [--lapse-map F]
                                            [--rows 5000] [--m 199] [--blocks N] [--dump F.npz]

Samples exactly as scripts/diagnose.py (unknown drivers drawn from training rows of the same group, range map, clip, shuffle,
shear map, lapse map, in that order). Writes STEM.csv (metric, var, band, value), lower is better unless noted:
  shear_p99_ratio  shear  band    p99 of sample vector shear / p99 of truth shear, layers by midpoint band (1 = right; GX2 / H4 target)
  ri_lt1_share     ri     band    share of layers with Richardson number < 1 (samples), with ri_lt1_truth next to it (closer = better)
  vcorr_sep        u|v|T|RH sep   mean |corr(sample departures) - corr(truth - ens mean)| over height pairs in a separation band (GF1 target)
  variogram        u|v|T|RH all   variogram score p=0.5 on 20 members, columns standardised by the 2021-23 climatology sd (GF1 target)
  block_crps       block  bN      with --blocks: CRPS / clim sd averaged over HAR block N's columns (GT1 "error by block")
  vcorr_nbr        block  bN-bN+1 with --blocks: vcorr error over height pairs across neighbouring blocks (GT1 target)
--dump writes the calibrated samples (x float16), truth (y), the row indices and months for reuse (GF4).
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.features import FEATURES, drivers
from tempest.generator.sample import Sampler, clip_ranges, standard_pressure, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.score import crps_ensemble, group_keys, variogram_score

H = np.asarray(HEIGHTS, float)
NH = len(H)
MID = 0.5 * (H[1:] + H[:-1])
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
SEP = [("0-1 km", 0, 1000), ("1-3 km", 1000, 3000), ("3-6 km", 3000, 6000), ("6+ km", 6000, 1e9)]


def sample_stack(model, calib, d, idx, m, rng, first_year, shuffle=False, cell=0, shear_map=None, lapse_map=None, device=None, chunk=400):
    """Calibrated samples (len(idx), m, 179) of the stack, as scripts/diagnose.py builds them (unknown drivers)."""
    sampler = Sampler(torch.load(model, map_location="cpu", weights_only=True), device=device)
    cal = spread.load(calib, model)
    year, cond = d["year"], np.asarray(d["cond"])
    keys = group_keys(cond)
    dc = [FEATURES.index(k) for k in drivers()]
    tr = np.flatnonzero(year < first_year)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[idx], "left"), np.searchsorted(keys[tr], keys[idx], "right")
    draws = tr[np.minimum(lo[:, None] + (rng.random((len(idx), m)) * np.maximum(hi - lo, 1)[:, None]).astype(np.int64), len(tr) - 1)]
    x = np.empty((len(idx), m, 4 * NH + 3), np.float32)
    for i in range(0, len(idx), chunk):
        sl = slice(i, i + chunk)
        rep = np.repeat(cond[idx[sl]], m, axis=0)
        rep[:, dc] = cond[draws[sl].ravel()][:, dc]
        x[sl] = clip_ranges(spread.apply(cal, sampler.profiles(rep).reshape(len(cond[idx[sl]]), m, -1), clip=False))
    if shuffle:
        from tempest.calibrate import shuffle as shuf_mod
        x = shuf_mod.apply(x, shuf_mod.group_template(d["target"], keys, year, idx, m, rng, first_year, cell=cell, n_lon=shuf_mod.grid_n_lon(d["cond"])))
    if shear_map:
        from tempest.calibrate import shear_map as smap
        x = smap.apply(dict(np.load(shear_map)), x)
    if lapse_map:
        from tempest.calibrate import lapse_map as lmap
        x = lmap.apply(dict(np.load(lapse_map)), x)
    return x


def shear_mag(u, v):
    return np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / np.diff(H)          # 1/s


def ri_lt1(prof, sp):
    """prof (..., 179) physical, sp (...) surface pressure -> (..., 43) bool Ri < 1 and (..., 43) finite."""
    u, v, T = prof[..., :NH], prof[..., NH:2 * NH], prof[..., 2 * NH:3 * NH].astype(np.float64)
    T = T + 273.15 if np.nanmedian(T) < 150 else T                                     # guard: Celsius targets
    sp = np.where(np.asarray(sp) < 2000, np.asarray(sp) * 100.0, sp)                 # guard: hPa
    p = sp[..., None] * standard_pressure(H) / standard_pressure(0.0)
    th = T * (1e5 / p) ** 0.286
    n2 = 9.81 / (0.5 * (th[..., 1:] + th[..., :-1])) * np.diff(th, axis=-1) / np.diff(H)
    ri = n2 / np.maximum(shear_mag(u, v) ** 2, 1e-12)
    ok = np.isfinite(ri)
    return (ri < 1) & ok, ok


def corr(a):
    a = a - a.mean(0)
    s = np.sqrt((a ** 2).mean(0)) + 1e-12
    return (a.T @ a) / len(a) / np.outer(s, s)


def vcorr_parts(x, y, cols):
    """|corr(sample departures) - corr(truth - ens mean)| over the given columns (pairs matrix)."""
    xm = x[..., cols].mean(1)
    cs = corr((x[..., cols] - xm[:, None]).reshape(-1, len(cols)).astype(np.float64))
    ct = corr((y[:, cols] - xm).astype(np.float64))
    return np.abs(cs - ct)


def metrics(x, y, clim_sd, blocks=0, rng=None):
    rng = rng or np.random.default_rng(0)
    rows = []
    add = lambda metric, v, b, val: rows.append(dict(metric=metric, var=v, band=b, value=float(val)))
    sx, sy = shear_mag(x[..., :NH], x[..., NH:2 * NH]), shear_mag(y[:, :NH], y[:, NH:2 * NH])
    sp_col = 4 * NH + 1
    rx, okx = ri_lt1(x, x[..., sp_col])
    ry, oky = ri_lt1(y, y[:, sp_col])
    for name, lo, hi in BANDS:
        b = (MID >= lo) & (MID < hi)
        add("shear_p99_ratio", "shear", name, np.percentile(sx[..., b], 99) / max(np.percentile(sy[:, b], 99), 1e-12))
        add("ri_lt1_share", "ri", name, rx[..., b].sum() / max(okx[..., b].sum(), 1))
        add("ri_lt1_truth", "ri", name, ry[:, b].sum() / max(oky[:, b].sum(), 1))
    dh = np.abs(H[:, None] - H[None, :])
    off = ~np.eye(NH, dtype=bool)
    sub = rng.choice(x.shape[1], min(20, x.shape[1]), replace=False)
    for i, v in enumerate(PROFILE):
        cols = np.arange(i * NH, (i + 1) * NH)
        e = vcorr_parts(x, y, cols)
        for name, lo, hi in SEP:
            add("vcorr_sep", v, name, e[off & (dh >= lo) & (dh < hi)].mean())
        sd = clim_sd[cols]
        add("variogram", v, "all", variogram_score(x[:, sub][..., cols] / sd, y[:, cols] / sd).mean())
    if blocks:
        from tempest.generator.s25_models import har_blocks
        bl = har_blocks(blocks, x.shape[-1])
        c = crps_ensemble(x, y) / clim_sd
        for b, cols in enumerate(bl):
            add("block_crps", "block", f"b{b}", c[:, cols].mean())
        hb = np.array_split(np.arange(NH), blocks)
        for b in range(blocks - 1):
            cols = np.concatenate([hb[b], hb[b + 1]])
            err = np.stack([vcorr_parts(x, y, i * NH + cols) for i in range(len(PROFILE))]).mean(0)
            na = len(hb[b])
            add("vcorr_nbr", "block", f"b{b}-b{b + 1}", err[:na, na:].mean())
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--template-cell", type=int, default=0)
    ap.add_argument("--shear-map")
    ap.add_argument("--lapse-map")
    ap.add_argument("--blocks", type=int, default=0)
    ap.add_argument("--dump")
    a = ap.parse_args()
    assert a.last_year <= 2025, "never the 2026 window"
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    d = load_npz(a.data)
    year = d["year"]
    pick = np.flatnonzero((year >= a.first_year) & (year <= a.last_year))
    idx = np.sort(rng.choice(pick, min(a.rows, len(pick)), replace=False))
    y = to_physical(np.asarray(d["target"][idx]))
    cal_idx = np.flatnonzero((year >= 2021) & (year <= 2023))
    clim_sd = np.maximum(to_physical(np.asarray(d["target"][np.sort(rng.choice(cal_idx, min(20000, len(cal_idx)), replace=False))])).std(0), 1e-6)
    x = sample_stack(a.model, a.calib, d, idx, a.m, rng, a.first_year, a.shuffle, a.template_cell, a.shear_map, a.lapse_map, a.device)
    if a.dump:
        c = np.asarray(d["cond"])[idx]
        doy = np.arctan2(c[:, FEATURES.index("doy_sin")], c[:, FEATURES.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25
        np.savez(a.dump, x=x.astype(np.float16), y=y, idx=idx, month=(group_keys(c) // 12) % 12 + 1, year=year[idx],
                 block=year[idx] * 100 + (doy // 7).astype(int))          # 7-day date blocks for the GF4 interval
    t = metrics(x, y, clim_sd, a.blocks, rng)
    t.to_csv(a.out + ".csv", index=False)
    print(t.round(4).to_string(index=False))
    print(f"wrote {a.out}.csv")


def _selfcheck():
    """Truth-like samples score near-perfect; a shrunk ensemble has shear ratio < 1."""
    rng = np.random.default_rng(1)
    n, m = 300, 30
    base = np.zeros(4 * NH + 3)
    base[2 * NH:3 * NH] = 300 - 0.0065 * H
    base[4 * NH + 1] = 90000.0
    walk = lambda *s: np.cumsum(rng.standard_normal(s + (NH,)), -1) * 0.5
    y = np.tile(base, (n, 1))
    y[:, :NH], y[:, NH:2 * NH] = walk(n), walk(n)
    x = np.tile(base, (n, m, 1))
    x[..., :NH], x[..., NH:2 * NH] = walk(n, m), walk(n, m)
    t = metrics(x, y, np.ones(4 * NH + 3), blocks=4, rng=rng)
    r = t[t.metric == "shear_p99_ratio"].value
    assert ((r > 0.8) & (r < 1.25)).all(), r
    x2 = x.copy()
    x2[..., :2 * NH] *= 0.3
    assert (metrics(x2, y, np.ones(4 * NH + 3), rng=rng).query("metric == 'shear_p99_ratio'").value < 0.5).all()
    assert len(t[t.metric == "block_crps"]) == 4 and len(t[t.metric == "vcorr_nbr"]) == 3
    still = np.tile(base, (2, 1))
    assert ri_lt1(still, still[:, 4 * NH + 1])[0].sum() == 0          # no shear, stable air: no layer under Ri 1
    print("s25_shape selfcheck ok")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
    else:
        main()
