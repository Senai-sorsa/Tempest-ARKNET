"""Parse the driver index files from fetch_indices into one monthly table (index = first day of month).

Columns: oni (ONI anomaly, 3-month season assigned to its centre month), qbo30, qbo50 (m/s), wwv (anomaly, m3).
"""
import os

import numpy as np
import pandas as pd

ONI_SEASONS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def read_oni(path):
    rows = [ln.split() for ln in open(path).read().splitlines()[1:] if ln.strip()]
    return pd.Series({pd.Timestamp(int(yr), ONI_SEASONS.index(s) + 1, 1): float(anom) for s, yr, _, anom in rows})


def read_qbo(path):
    """First block ("ORIGINAL DATA") of a CPC qbo.uXX.index file; fixed width, -999.9 = missing."""
    out = {}
    for ln in open(path).read().splitlines()[4:]:
        if not ln[:4].isdigit():
            break
        for m in range(12):
            v = float(ln[4 + 7 * m:11 + 7 * m])
            if v > -999:
                out[pd.Timestamp(int(ln[:4]), m + 1, 1)] = v
    return pd.Series(out)


def read_wwv(path):
    out = {}
    for ln in open(path).read().splitlines():
        p = ln.split()
        if len(p) == 3 and p[0].isdigit() and len(p[0]) == 6:
            out[pd.Timestamp(int(p[0][:4]), int(p[0][4:]), 1)] = float(p[2])
    return pd.Series(out)


def load(root="data/raw/indices"):
    j = lambda n: os.path.join(root, n)
    return pd.DataFrame(dict(oni=read_oni(j("oni.txt")), qbo30=read_qbo(j("qbo_u30.txt")),
                             qbo50=read_qbo(j("qbo_u50.txt")), wwv=read_wwv(j("wwv.txt")))).sort_index()


def at(table, times):
    """Index values for each timestamp's month -> (N, 4) array in column order oni, qbo30, qbo50, wwv."""
    months = pd.DatetimeIndex(times).to_period("M").to_timestamp()
    return table.reindex(months)[["oni", "qbo30", "qbo50", "wwv"]].to_numpy(np.float32)


COLS = ["oni", "qbo30", "qbo50", "wwv"]


def read_gmst(path):
    """NASA GISTEMP v4 monthly CSV (global mean surface temperature anomaly, K) -> monthly Series. Row 1 is a title;
    columns Year, Jan..Dec; "***" is missing."""
    out = {}
    for ln in open(path, encoding="utf-8").read().splitlines()[2:]:
        p = ln.split(",")
        if len(p) < 13 or not p[0].isdigit():
            continue
        for m in range(12):
            try:
                out[pd.Timestamp(int(p[0]), m + 1, 1)] = float(p[1 + m])
            except ValueError:
                pass
    return pd.Series(out).sort_index()


def gmst_table(root="data/raw/indices", window=60):
    """Smoothed GMST known at the START of each month: the mean of the previous `window` monthly anomalies (a trailing
    mean, so nothing from the future leaks into a training row). Extended with the last value for later months, which
    is what a query about the future gets ("last known value carried forward")."""
    s = read_gmst(os.path.join(root, "gistemp.csv"))
    sm = s.rolling(window, min_periods=window).mean().shift(1)
    last = s.index[-1] + pd.DateOffset(months=1)
    sm.loc[last] = s.iloc[-window:].mean()  # the month after the last datum is known from the data so far
    return sm.dropna()


def gmst_at(sm, times):
    """Smoothed GMST for each timestamp's month (float32); months past the table carry the last value forward."""
    months = pd.DatetimeIndex(times).to_period("M").to_timestamp()
    i = np.clip(sm.index.searchsorted(months, side="right") - 1, 0, len(sm) - 1)  # latest table month at or before each one
    return sm.to_numpy()[i].astype(np.float32)


def oni_lag(table, times, months=3):
    """ONI of `months` months before each timestamp's month (float32)."""
    return at(table, pd.DatetimeIndex(times) - pd.DateOffset(months=months))[:, 0]


def analog(table, times, lag_days, m, rng, before, k=8):
    """Driver values for m samples per time when only values `lag_days` old are known (PLAN A6, option 5).
    For each time, the k past months of the same calendar month (year < before) whose values lag_days earlier are
    nearest (standardised) to this time's lag-day-old values; each sample takes one of them's own month values.
    -> (N, m, 4) in COLS order (same as at()). Tested on 2024-25: beats random draws up to ~90 days, ties at 180."""
    times = pd.DatetimeIndex(times)
    lag = pd.Timedelta(days=lag_days)
    sd = np.nanstd(table[COLS].to_numpy(np.float64), 0)
    now = at(table, times - lag) / sd
    out = np.full((len(times), m, len(COLS)), np.nan, np.float32)
    for mo in np.unique(times.month):
        r = np.flatnonzero(times.month == mo)
        cand = table.index[(table.index.month == mo) & (table.index.year < before)]
        cand = cand[np.isfinite(at(table, cand - lag)).all(1) & np.isfinite(at(table, cand)).all(1)]
        kk = min(k, len(cand))
        near = np.argsort(((now[r][:, None] - (at(table, cand - lag) / sd)[None]) ** 2).sum(-1), 1)[:, :kk]
        out[r] = at(table, cand[near[np.arange(len(r))[:, None], rng.integers(0, kk, (len(r), m))].ravel()]).reshape(len(r), m, -1)
    return out


def feature_extras(names, table, gm, times):
    """Keyword arguments for features.features() that the active feature list needs beyond the original 13:
    gmst (from gmst_table, `gm`) and the 3-month lagged ONI. Empty for the original list."""
    out = {}
    if "gmst" in names:
        out["gmst"] = gmst_at(gm, times)
    if "oni_lag3" in names:
        out["oni_lag3"] = oni_lag(table, times)
    return out
