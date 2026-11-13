"""G2-7: shape scores of the tool after each stage of the stack, against balloons. REPORT ONLY (no pass / kill).
Stages (see kit_common.STAGES): range map only -> + shuffle -> + shear map -> + lapse map (shipped). The stage switch removes keys from
api._assets()["post"] in memory and puts them back; nothing on disk changes. ("Raw network without the range map" is not switchable there and is left out.)
Cases: EPZ and MAF balloons, 00Z and 12Z, 2024-25. Rows also printed: the balloons themselves and ERA5 at the same hours.
  A  share of layers with Richardson number < 1, per height band (too many = too much shear for the stability)
  B  mean count per profile, below 3 km, of layers where T rises by more than 2 K
  C  band-depth rank histogram of u, v, T (10 bins): largest deviation of a bin from 0.10 (0 = truth looks like a member)

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_shape_scores.py                  # 400 cases per group, about 30-40 min, 3 threads
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_shape_scores.py --per-group 3 --seeds 1   # smoke test, 1 min
Result: docs/results/logs/kit_b1_shape_scores.log
"""
import argparse

import numpy as np

import kit_common as K

MID = 0.5 * (K.H[1:] + K.H[:-1])
BMASK = [(MID >= lo) & (MID < hi) for _, lo, hi in K.BANDS]


def ri_counts(u, v, T, p):
    """-> (4, 2) per band: layers with Ri < 1, layers with a finite Ri. Inputs (..., 44)."""
    ri = K.n2(T, p) / np.maximum((K.shear_mag(u, v) / 1000.0) ** 2, 1e-12)
    ok = np.isfinite(ri)
    return np.array([[((ri < 1) & ok)[..., m].sum(), ok[..., m].sum()] for m in BMASK], float)


def inversions(T):
    """Per profile: layers below 3 km where T rises by more than 2 K."""
    return (np.diff(T, axis=-1)[..., K.H[1:] <= 3000.0] > 2.0).sum(-1)


def depth_bin(members, truth, rng):
    """Bin 0-9 of the truth's band depth among the members (None when the truth has under 30 heights)."""
    ok = np.isfinite(truth)
    if ok.sum() < 30:
        return None
    x = np.vstack([truth[ok], members[:, ok]])
    n = len(x)
    r = x.argsort(0).argsort(0) + 1
    dep = (r * (n - r + 1)).mean(1) + 1e-9 * rng.random(n)     # tiny noise breaks ties at random
    return min(9, int((dep < dep[0]).sum() * 10 // n))


class Acc:
    def __init__(self):
        self.ri, self.inv, self.n, self.hist = np.zeros((4, 2)), 0.0, 0, {k: np.zeros(10) for k in "uvT"}

    def add(self, u, v, T, p):
        self.ri += ri_counts(u, v, T, p)
        self.inv += float(np.mean(inversions(T)))
        self.n += 1

    def row(self):
        ri = self.ri[:, 0] / np.maximum(self.ri[:, 1], 1)
        dev = [np.abs(h / max(h.sum(), 1) - 0.1).max() if h.sum() else np.nan for h in self.hist.values()]
        return list(ri) + [self.inv / max(self.n, 1)] + dev


def cases(per_group, rng):
    for sid in (K.EPZ, K.MAF):
        t, b = K.balloon(sid)
        full = np.isfinite(b["u"]).sum(1) >= 30
        for hour in (0, 12):
            idx = np.flatnonzero((t.year >= 2024) & (t.year <= 2025) & (t.hour == hour) & full)
            for k in rng.permutation(idx)[:per_group]:
                yield sid, t[k], {q: b[q][k] for q in b}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    todo = list(cases(a.per_group, rng))
    acc = {(s, k): Acc() for s in K.STAGES for k in range(a.seeds)}
    truth, era, skipped = Acc(), Acc(), 0
    era_cache = {}
    for sid, t, b in todo:
        lat, lon, elev = K.station_pos(sid)
        try:
            runs = {(s, k): K.tool(lat, lon, t, seed=1000 * k + int(t.dayofyear), elevation=elev, stage=s) for s in K.STAGES for k in range(a.seeds)}
        except ValueError:        # hour outside what the installed assets cover (for example a night hour with day-only assets)
            skipped += 1
            continue
        truth.add(b["u"], b["v"], b["T"], b["p"])
        if sid not in era_cache:
            era_cache[sid] = K.era5_at(lat, lon, [x[1] for x in todo if x[0] == sid])
        et, e = era_cache[sid]
        j = et.get_indexer([t])[0]
        if j >= 0:
            era.add(e["u"][j], e["v"][j], e["T"][j], b["p"])
        for key, atm in runs.items():
            acc[key].add(atm["u"], atm["v"], atm["T"], atm["p"])
            for q in "uvT":
                bin_ = depth_bin(np.asarray(atm[q]), b[q], rng)
                if bin_ is not None:
                    acc[key].hist[q][bin_] += 1
    head = "stage                      " + "".join(f"Ri<1 {n:<9}" for n, _, _ in K.BANDS) + "T-rises<3km  depth-dev u     v     T"
    fmt = lambda name, r: f"{name:<27}" + "".join(f"{x:<14.3f}" for x in r[:4]) + f"{r[4]:<13.3f}" + "".join(f"{x:<6.3f}" for x in r[5:])   # noqa: E731
    lines = [f"G2-7 shape scores per stage: {truth.n} cases used, {skipped} skipped (hour not covered), seeds {a.seeds}", head,
             fmt("balloons (truth)", truth.row()[:5]), fmt(f"ERA5 ({era.n} cases)", era.row()[:5])]
    for s in K.STAGES:
        rows = np.array([acc[(s, k)].row() for k in range(a.seeds)])
        lines.append(fmt(s, rows.mean(0)))
        if a.seeds > 1:
            lines.append(fmt("   seed spread (max-min)", rows.max(0) - rows.min(0)))
    lines.append("Read it like this: a stage is good when its Ri<1 share and T-rise count are close to the balloon row and its depth-dev is small (about 0.03 is noise at 600 cases).")
    K.report("b1_shape_scores", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    h = np.zeros(10)
    for _ in range(3000):                                   # truth drawn like a member -> flat histogram
        x = rng.standard_normal((200, 44)).cumsum(1)
        h[depth_bin(x[1:], x[0], rng)] += 1
    assert np.abs(h / h.sum() - 0.1).max() < 0.03, h
    T = 288.0 - 0.0065 * K.H
    p = 1e5 * (T / 288.0) ** 5.256
    assert ri_counts(0 * K.H, 0 * K.H, T, p)[:, 0].sum() == 0      # no shear, stable air: no layer under Ri 1
    assert ri_counts(K.H * 0.05, 0 * K.H, T, p)[:, 0].sum() == 43  # 50 m/s per km: every layer under Ri 1
    T2 = T.copy()
    T2[5] += 5
    assert inversions(T) == 0 and inversions(T2) == 1


_selfcheck()
if __name__ == "__main__":
    main()
