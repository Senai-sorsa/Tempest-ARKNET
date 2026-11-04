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
