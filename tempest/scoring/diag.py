"""Why a forecast misses: per output column and summarised per variable x height band and per month.

    bias        mean(ensemble mean - truth), in the variable's units (sign = model too high / too low)
    rmse        of the ensemble mean
    ss_ratio    spread / skill: ensemble std (m-corrected) / rmse. 1 = right width, < 1 too narrow, > 1 too wide
    miss_lo/hi  share of truths below / above the 99 % range (each should be 0.005); lopsided = skew or bias
    pit_lo/hi   share of truths below the lowest / above the highest member (each ~ 1/(m+1))
Printed as tables and written to <stem>_diag.csv and <stem>_diag_month.csv.
"""
import numpy as np
import pandas as pd


def columns(x, y, p=0.99):
    """x (N, m, D) samples, y (N, D) truth -> DataFrame, one row per column."""
    n, m, d = x.shape
    k = max(1, int(round((1 - p) / 2 * (m + 1))))
    out = {k_: np.empty(d) for k_ in ("bias", "rmse", "ss_ratio", "miss_lo", "miss_hi", "pit_lo", "pit_hi")}
    for j in range(d):  # per column keeps temporaries small for big N x m
        xj, yj = x[..., j].astype(np.float64), y[:, j].astype(np.float64)
        e = xj.mean(1) - yj
        rmse = np.sqrt((e ** 2).mean())
        sd = np.sqrt(xj.var(1, ddof=1).mean() * (m + 1) / m)
        s = np.partition(xj, [0, k - 1, m - k, m - 1], axis=1)
        out["bias"][j], out["rmse"][j] = e.mean(), rmse
        out["ss_ratio"][j] = sd / max(rmse, 1e-12)
        out["miss_lo"][j], out["miss_hi"][j] = (yj < s[:, k - 1]).mean(), (yj > s[:, m - k]).mean()
        out["pit_lo"][j], out["pit_hi"][j] = (yj < s[:, 0]).mean(), (yj > s[:, m - 1]).mean()
    return pd.DataFrame(out)


def summarise(col, groups):
    """col: per-column DataFrame; groups: list of (var, band, boolean mask over columns)."""
    return pd.DataFrame([dict(var=v, band=b, **col[sel].mean(numeric_only=True).to_dict(),
                              worst_miss=(col.miss_lo + col.miss_hi)[sel].max()) for v, b, sel in groups])


def by_month(x, y, month, var_slices, p=0.99):
    """Coverage and bias per calendar month and variable (columns pooled), to spot seasonal failures."""
    m = x.shape[1]
    k = max(1, int(round((1 - p) / 2 * (m + 1))))
    rows = []
    for mo in np.unique(month):
        r = month == mo
        for v, sl in var_slices:
            xs, ys = x[r][..., sl], y[r][:, sl]
            s = np.partition(xs, [k - 1, m - k], axis=1)
            rows.append(dict(month=int(mo), var=v, n=int(r.sum()), bias=float((xs.mean(1) - ys).mean()),
                             cov99=float(((ys >= s[:, k - 1]) & (ys <= s[:, m - k])).mean())))
    return pd.DataFrame(rows)


def report(stem, x, y, names, groups, month=None, var_slices=None):
    col = columns(x, y)
    col.insert(0, "column", names)
    col.to_csv(stem + "_diag.csv", index=False)
    summ = summarise(col, groups)
    with pd.option_context("display.width", 220, "display.float_format", "{:.4f}".format):
        print("\nDIAG (known drivers): bias, width (ss_ratio ~1 ideal) and which side of the 99 % range misses")
        print(summ.to_string(index=False))
        worst = col.assign(miss=col.miss_lo + col.miss_hi).nlargest(10, "miss")
        print("\nDIAG worst 10 columns by 99 % miss rate (target 0.01):")
        print(worst.to_string(index=False))
        if month is not None:
            mon = by_month(x, y, month, var_slices)
            mon.to_csv(stem + "_diag_month.csv", index=False)
            print("\nDIAG 99 % coverage by month (rows: month, cols: variable):")
            print(mon.pivot(index="month", columns="var", values="cov99").to_string())
    return summ


def headline(sets, truth, day, groups, p=0.99, n_boot=1000, seed=0):
    """Band table with 95 % intervals from a bootstrap over whole days (rows on one day move together, so resampling
    rows would give falsely narrow intervals). sets: dict name -> (N, m, D) samples, needs clim, known, unknown and
    optionally clim15 (climatology from the last 15 years before the test, so skill is not just "knows it got warmer").
    skill = 1 - CRPS / CRPS_clim; mae = error of the per-column median (the best guess); cov99 = inside the 99 % range."""
    from tempest.scoring.score import coverage90, crps_ensemble  # late import: score imports diag
    masks = np.stack([sel for _, _, sel in groups], 1).astype(np.float64)
    masks /= masks.sum(0)
    band = lambda a: a.astype(np.float64) @ masks  # (N, D) -> (N, G) per-row band means
    stat = {}
    for k, x in sets.items():
        stat[f"crps_{k}"] = band(crps_ensemble(x, truth))
        stat[f"mae_{k}"] = band(np.abs(np.median(x, 1) - truth))
    for k in ("known", "unknown"):
        stat[f"cov99_{k}"] = band(coverage90(sets[k], truth, p))
    _, inv = np.unique(day, return_inverse=True)
    rng = np.random.default_rng(seed)
    nd = inv.max() + 1
    c = np.vstack([np.ones(nd), rng.multinomial(nd, np.full(nd, 1 / nd), n_boot)])  # times each day is drawn; row 0 = as is
    tot = c @ np.bincount(inv, minlength=nd)  # rows per replicate
    daysum = lambda v: np.stack([np.bincount(inv, v[:, g], nd) for g in range(v.shape[1])], 1)  # (nd, G)
    mean = {k: (c @ daysum(v)) / tot[:, None] for k, v in stat.items()}  # (1 + n_boot, G)
    out = {"var": [v for v, _, _ in groups], "band": [b for _, b, _ in groups]}

    def put(name, val):
        out[name] = val[0]
        out[name + "_lo"], out[name + "_hi"] = np.percentile(val[1:], [2.5, 97.5], 0)
    for k in ("known", "unknown"):
        put(f"skill_{k}", 1 - mean[f"crps_{k}"] / mean["crps_clim"])
        if "crps_clim15" in mean:
            put(f"skill15_{k}", 1 - mean[f"crps_{k}"] / mean["crps_clim15"])
    if "crps_gauss" in mean and "crps_clim15" in mean:  # IL-111: Gaussian (Earth-GRAM style) baseline, additive columns
        put("skill15_gauss", 1 - mean["crps_gauss"] / mean["crps_clim15"])
        for k in ("known", "unknown"):  # margin of the model over the Gaussian baseline, in units of clim15 CRPS (> 0 = model wins)
            put(f"margin_gauss_{k}", (mean["crps_gauss"] - mean[f"crps_{k}"]) / mean["crps_clim15"])
    for k in ("clim", "clim15", "known", "unknown"):
        if f"mae_{k}" in mean:
            out[f"mae_{k}"] = mean[f"mae_{k}"][0]
    put("cov99_known", mean["cov99_known"])
    put("cov99_unknown", mean["cov99_unknown"])
    return pd.DataFrame(out)


def print_headline(tab, path):
    """Compact print: value [95 % interval]; also saved in full to path."""
    tab.to_csv(path, index=False)
    f = lambda c: tab.apply(lambda r: f"{r[c]:.3f} [{r[c + '_lo']:.3f}, {r[c + '_hi']:.3f}]", axis=1)
    show = tab[["var", "band"]].copy()
    for c in ("skill_known", "skill_unknown", "skill15_known", "skill15_unknown", "skill15_gauss", "margin_gauss_unknown",
              "cov99_known", "cov99_unknown"):
        if c in tab:
            show[c] = f(c)
    for c in ("mae_clim", "mae_clim15", "mae_known", "mae_unknown"):
        if c in tab:
            show[c] = tab[c].map("{:.3f}".format)
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        print("\nHEADLINE (95 % intervals from a day-block bootstrap; skill15 = vs climatology of the last 15 years "
              "before the test, i.e. with warming included; unknown = drivers the tool would not know):")
        print(show.to_string(index=False))
