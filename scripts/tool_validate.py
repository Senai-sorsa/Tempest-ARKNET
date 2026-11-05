"""Validate the standalone tool against ERA5 on the development years (PHASE5_TOOL.md 5.7).

    PYTHONPATH=. python scripts/tool_validate.py [--rows 1000] [--data data/train/pilot80_dpd.npz] [--headline models/generator_80_p2f_cal2021_headline.csv]

Takes held-out 2024-25 rows (place, date, hour, observed climate indices), runs them through the TOOL's numpy engine and range calibration (not the torch sampler),
and reports, per variable x height band, the share of ERA5 truths inside the 99 % range with day-block 95 % intervals. Compared with the main scorer's
`cov99_known` for the same model (same drivers: observed), which should agree within sampling noise. Not a replacement for score.py: smaller sample, one seed.
"""
import argparse

import numpy as np
import pandas as pd

from tempest_weather import _core, api
from tempest.generator.features import FEATURES
from tempest.generator.sample import to_physical
from tempest.generator.train import load_npz
from tempest.scoring.score import band_masks, coverage90


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=1000)
    ap.add_argument("--data", default="data/train/pilot80_dpd.npz")
    ap.add_argument("--headline", default="models/generator_80_p2f_cal2021_headline.csv")
    ap.add_argument("--assets", default="tempest_weather/assets")
    a = ap.parse_args()
    A = api._assets(a.assets)
    d = load_npz(a.data)
    year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
    rng = np.random.default_rng(0)
    rows = np.sort(rng.choice(np.flatnonzero((year >= 2024) & (year <= 2025)), a.rows, replace=False))
    truth = to_physical(np.asarray(d["target"][rows]))
    m = api.M_CAL
    phys = A["net"].profiles(np.repeat(cond[rows], m, 0), rng)
    phys = _core.calibrate(A["calib"], phys.reshape(len(rows), m, -1))
    doy = np.round(np.arctan2(cond[rows, FEATURES.index("doy_sin")], cond[rows, FEATURES.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25).astype(np.int64)
    _, inv = np.unique(year[rows].astype(np.int64) * 1000 + doy, return_inverse=True)
    nd = inv.max() + 1
    boot = np.vstack([np.ones(nd), np.random.default_rng(1).multinomial(nd, np.full(nd, 1 / nd), 500)])
    cnt = np.bincount(inv, minlength=nd)
    cov = coverage90(phys, truth, 0.99).astype(float)
    rows_out = []
    for v, b, sel in band_masks():
        per = cov[:, sel].mean(1)
        mm = (boot @ np.bincount(inv, per, nd)) / (boot @ cnt)
        rows_out.append(dict(var=v, band=b, tool_cov99=mm[0], lo=np.percentile(mm[1:], 2.5), hi=np.percentile(mm[1:], 97.5)))
    t = pd.DataFrame(rows_out)
    try:
        h = pd.read_csv(a.headline)[["var", "band", "cov99_known"]]
        t = t.merge(h, on=["var", "band"], how="left")
        t["agree"] = (t.cov99_known >= t.lo) & (t.cov99_known <= t.hi)
    except FileNotFoundError:
        pass
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        print(t.to_string(index=False))
    print(f"mean |cov99 - 0.99| through the tool: {(t.tool_cov99 - 0.99).abs().mean():.4f}; min {t.tool_cov99.min():.4f}",
          f"; main scorer's number inside the tool's interval in {int(t.agree.sum())} of {len(t)} cells" if "agree" in t else "")
    t.to_csv("models/tool_validate.csv", index=False)


if __name__ == "__main__":
    main()
