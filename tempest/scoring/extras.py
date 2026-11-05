"""Extra evaluation tables, written to <stem>_extras_*.csv. Additive only: nothing in the old outputs changes.

- pit:       10-bin PIT histogram of the truth among the samples, per variable x height band (flat = calibrated).
- coverage:  share of truths inside the central 50 / 80 / 90 / 99 % ranges, per variable x band (m = 199 samples make
             all four exact order statistics).
- wind:      error of the median wind (from the median u and v): speed MAE/RMSE (m/s) and direction MAE (degrees, only
             where the true speed is above 2 m/s, since direction of a calm wind is noise), per height band.
- worst:     the 10 worst variable x band x month cells and the 10 worst columns by distance of cov99 from 0.99.
"""
import numpy as np
import pandas as pd

from tempest.profiles.to_heights import HEIGHTS, PROFILE


def _cov(x, y, p):
    from tempest.scoring.score import coverage90
    return coverage90(x, y, p)


def pit_table(x, y, groups, bins=10):
    """x (N, m, D), y (N, D) -> rows (var, band, bin_0..bin_9) with the share of truths in each PIT bin."""
    m = x.shape[1]
    rank = ((x < y[:, None]).sum(1) + 0.5 * (x == y[:, None]).sum(1)) / m  # randomised ties are not needed: ties are rare
    idx = np.minimum((rank * bins).astype(int), bins - 1)
    rows = []
    for v, b, sel in groups:
        h = np.bincount(idx[:, sel].ravel(), minlength=bins) / idx[:, sel].size
        rows.append(dict(var=v, band=b, **{f"bin_{i}": h[i] for i in range(bins)}))
    return pd.DataFrame(rows)


def coverage_table(x, y, groups, levels=(0.5, 0.8, 0.9, 0.99)):
    cov = {p: _cov(x, y, p).mean(0) for p in levels}
    return pd.DataFrame([dict(var=v, band=b, **{f"cov{int(p * 100)}": cov[p][sel].mean() for p in levels})
                         for v, b, sel in groups])


def wind_table(x, y):
    """Speed and direction error of the median wind, per height band."""
    n = len(HEIGHTS)
    iu, iv = PROFILE.index("u") * n, PROFILE.index("v") * n
    mu, mv = np.median(x[..., iu:iu + n], 1), np.median(x[..., iv:iv + n], 1)
    tu, tv = y[:, iu:iu + n], y[:, iv:iv + n]
    sp_m, sp_t = np.hypot(mu, mv), np.hypot(tu, tv)
    d = np.degrees(np.arctan2(mu, mv) - np.arctan2(tu, tv))
    d = np.abs((d + 180) % 360 - 180)
    rows = []
    for lo, hi in ((0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)):
        s = (HEIGHTS >= lo) & (HEIGHTS < hi)
        ok = (sp_t[:, s] > 2.0)
        rows.append(dict(band=f"{lo / 1000:g}-{min(hi, 18000) / 1000:g} km", speed_mae=np.abs(sp_m - sp_t)[:, s].mean(),
                         speed_rmse=np.sqrt(((sp_m - sp_t)[:, s] ** 2).mean()),
                         vector_rmse=np.sqrt(((mu - tu)[:, s] ** 2 + (mv - tv)[:, s] ** 2).mean()),
                         dir_mae_deg=d[:, s][ok].mean(), dir_share_used=ok.mean()))
    return pd.DataFrame(rows)


def worst_table(x, y, groups, month, names):
    """Worst variable x band x month cells and worst columns by |cov99 - 0.99|."""
    c99 = _cov(x, y, 0.99)
    rows = []
    for mo in np.unique(month):
        r = month == mo
        for v, b, sel in groups:
            rows.append(dict(var=v, band=b, month=int(mo), n=int(r.sum()), cov99=c99[r][:, sel].mean()))
    cells = pd.DataFrame(rows).assign(dev=lambda t: (t.cov99 - 0.99).abs()).nlargest(10, "dev")
    col = pd.DataFrame(dict(column=names, cov99=c99.mean(0))).assign(dev=lambda t: (t.cov99 - 0.99).abs()).nlargest(10, "dev")
    return cells, col


def write(stem, x, y, groups, month, names, label="known"):
    """Compute and save all four tables for sample set x (N, m, D) and truth y; print a compact summary."""
    pit, cov, wind = pit_table(x, y, groups), coverage_table(x, y, groups), wind_table(x, y)
    cells, col = worst_table(x, y, groups, month, names)
    for name, t in (("pit", pit), ("coverage", cov), ("wind", wind), ("worst_cells", cells), ("worst_columns", col)):
        t.to_csv(f"{stem}_extras_{name}.csv", index=False)
    with pd.option_context("display.width", 220, "display.float_format", "{:.4f}".format):
        print(f"\nEXTRAS ({label} drivers): coverage at 50/80/90/99 % (targets 0.50/0.80/0.90/0.99)")
        print(cov.to_string(index=False))
        print("\nEXTRAS wind: error of the median wind")
        print(wind.to_string(index=False))
        print("\nEXTRAS worst 10 variable x band x month cells by distance of cov99 from 0.99:")
        print(cells.to_string(index=False))
        print("\nEXTRAS worst 10 columns:")
        print(col.to_string(index=False))
    return pit, cov, wind, cells, col
