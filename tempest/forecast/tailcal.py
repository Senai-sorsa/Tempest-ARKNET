"""TAILCAL (New_Plan 17, UR1): fix the far tails of a member set per lead, touch nothing else. Opt-in; nothing in the tool calls it yet.

For each row and column the members outside the row's own 90 % range (q05 = 10th lowest, q95 = 10th highest of 199, the scorer's rule) are
moved away from (factor > 1) or toward (factor < 1) that range:
    x < q05:  q05 - f_lo (q05 - x)          x > q95:  q95 + f_hi (x - q95)
one factor per variable x lead x side, pooled over heights. The map rises with x, so member ranks (and the Schaake order) do not change, the
members inside the 90 % range are bit-identical and the scorer's 90 % range is exactly unchanged. Because the map rises, the stretched set's
lowest member is the map of the old one, so a factor is fitted from four order statistics per row and column without touching the members:
f_lo is the grid value whose share of truths below the stretched 99 % range is nearest 0.005 (the same for f_hi above), i.e. the 99 % range
covers 99 % in the scorer's own sense (lowest to highest member for m = 199).
Factors are smoothed across the leads (running mean of neighbours, weights 1-2-1) and held to GRID.

    tab = fit(members, truth, lead, var_of_col)     # members (n, m, C), truth (n, C), lead (n,) any labels, var_of_col (C,) labels
    x2 = apply(tab, members, lead, var_of_col)      # same shape as members
"""
import numpy as np

GRID = np.round(np.arange(0.60, 3.0001, 0.02), 2)
TARGET = 0.005                         # each side of the 99 % range


def _k(m, p):
    """the scorer's rule (tempest.scoring.score.coverage90): central p range = k-th lowest to k-th highest member, k = (1 - p) / 2 (m + 1)."""
    return max(1, int(round((1 - p) / 2 * (m + 1))))


def quantiles(members):
    """members (n, m, C) -> (4, n, C): the k-th lowest / highest members that bound the scorer's 99 % and 90 % ranges (m = 199: the lowest and
    highest member, and the 10th lowest / highest), in the order (lo99, lo90, hi90, hi99)."""
    x = np.asarray(members, np.float32)
    m = x.shape[1]
    k99, k90 = _k(m, 0.99), _k(m, 0.90)
    s = np.partition(x, sorted({k99 - 1, k90 - 1, m - k90, m - k99}), axis=1)
    return np.stack([s[:, k99 - 1], s[:, k90 - 1], s[:, m - k90], s[:, m - k99]])


def _best(miss_by_f):
    """miss share for each grid factor -> the factor nearest TARGET (ties: the smaller factor)."""
    return float(GRID[int(np.argmin(np.abs(np.asarray(miss_by_f) - TARGET)))])


def fit_from_quantiles(q, truth, lead, var_of_col, smooth=True, min_rows=200):
    """q (4, n, C) from quantiles(), truth (n, C), lead (n,), var_of_col (C,) -> table dict(leads, vars, lo, hi (L, V), n (L, V))."""
    q005, q05, q95, q995 = (np.asarray(x, np.float64) for x in q)
    y = np.asarray(truth, np.float64)
    leads, vars_ = np.unique(lead), np.unique(var_of_col)
    lo, hi, nn = (np.ones((len(leads), len(vars_))) for _ in range(3))
    for i, L in enumerate(leads):
        r = lead == L
        for j, v in enumerate(vars_):
            c = var_of_col == v
            a, b, cc, d, t = (x[r][:, c].ravel() for x in (q005, q05, q95, q995, y))
            ok = np.isfinite(a) & np.isfinite(d) & np.isfinite(t)
            a, b, cc, d, t = a[ok], b[ok], cc[ok], d[ok], t[ok]
            nn[i, j] = r.sum()
            if r.sum() < min_rows:
                continue                                       # too few rows: factor 1 (no change)
            lo[i, j] = _best([np.mean(t < b - f * (b - a)) for f in GRID])
            hi[i, j] = _best([np.mean(t > cc + f * (d - cc)) for f in GRID])
    fitted = nn >= min_rows
    if smooth and len(leads) > 2:                                      # 1-2-1 over neighbouring leads, using fitted cells only; a thin cell stays 1
        k = np.array([1.0, 2.0, 1.0])
        for arr in (lo, hi):
            pad, pw = np.vstack([arr[:1], arr, arr[-1:]]), np.vstack([fitted[:1], fitted, fitted[-1:]]).astype(float)
            sm = np.stack([(pad[i:i + 3] * pw[i:i + 3] * k[:, None]).sum(0) / np.maximum((pw[i:i + 3] * k[:, None]).sum(0), 1e-12) for i in range(len(leads))])
            arr[:] = np.where(fitted, np.clip(sm, GRID[0], GRID[-1]), 1.0)
    return dict(leads=leads, vars=vars_, lo=lo, hi=hi, n=nn)


def fit(members, truth, lead, var_of_col, **kw):
    return fit_from_quantiles(quantiles(members), truth, np.asarray(lead), np.asarray(var_of_col), **kw)


def factors_for(tab, lead, var_of_col):
    """-> (f_lo, f_hi) each (n, C); a lead or variable not in the table gets 1."""
    li = {L: i for i, L in enumerate(tab["leads"].tolist())}
    vi = {v: j for j, v in enumerate(tab["vars"].tolist())}
    rows = np.array([li.get(L, -1) for L in np.asarray(lead).tolist()])
    cols = np.array([vi.get(v, -1) for v in np.asarray(var_of_col).tolist()])
    out = []
    for t in (tab["lo"], tab["hi"]):
        f = t[np.maximum(rows, 0)][:, np.maximum(cols, 0)]
        f[rows < 0] = 1.0
        f[:, cols < 0] = 1.0
        out.append(f)
    return out


BOUNDS = {"RH": (0.0, 100.0)}          # a stretched tail is held inside these (RH in %); the map stays non-decreasing


def apply(tab, members, lead, var_of_col, bounds=BOUNDS):
    x = np.asarray(members, np.float32)
    _, q05, q95, _ = quantiles(x)
    flo, fhi = factors_for(tab, lead, var_of_col)
    lo_side, hi_side = x < q05[:, None], x > q95[:, None]
    out = np.where(lo_side, q05[:, None] - flo[:, None] * (q05[:, None] - x), x)
    out = np.where(hi_side, q95[:, None] + fhi[:, None] * (x - q95[:, None]), out)
    moved = out != x
    for v, (b0, b1) in (bounds or {}).items():                         # only moved members are held inside the bounds; the rest stay bit-identical
        c = np.asarray(var_of_col) == v
        if c.any():
            out[:, :, c] = np.where(moved[:, :, c], np.clip(out[:, :, c], b0, b1), out[:, :, c])
    return out.astype(np.float32)


def save(path, tab):
    np.savez(path, **tab)


def load(path):
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}
