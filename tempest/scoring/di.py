"""Dissimilarity index (area of applicability, Meyer & Pebesma 2021) of grid points w.r.t. the training grid (LOOP3 L3-28).

    python -m tempest.scoring.di --train data/train/pilot80_dpd.npz --data data/train/denver_full_fill_dpd.npz

DI(point) = distance to the nearest training point in standardised location inputs / mean nearest-neighbour distance
between training points. Training points have DI ~ 1 against each other; the AOA threshold is the largest training DI
(leave-self-out). Rows of the same point share one DI, so it is computed per unique grid point.
shortcut: location inputs only, equal weights (no variable importance): time and driver inputs are shared by all
regions, and the test years lie outside the training years everywhere, so they would flag every test row; add them
with importance weights when the global model trains on many boxes (G2).
"""
import argparse

import numpy as np

from tempest.generator.features import FEATURES
from tempest.generator.train import load_npz

LOC = ["lat", "lon", "elev_site", "elev_grid"]


def points(path, last_year=2025):
    """Unique location rows (P, 4) of a set; years after last_year are never read into the result (2026 guard)."""
    d = load_npz(path)
    keep = np.flatnonzero(d["year"] <= last_year)
    c = np.asarray(d["cond"])[keep][:, [FEATURES.index(k) for k in LOC]]
    return np.unique(np.round(c, 3), axis=0)


def fit(train_pts):
    """-> dict(mu, sd, ref, dbar, thr) from training points."""
    mu, sd = train_pts.mean(0), train_pts.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    z = (train_pts - mu) / sd
    d = np.linalg.norm(z[:, None] - z[None], axis=-1)
    np.fill_diagonal(d, np.inf)
    nn = d.min(1)
    dbar = nn.mean()
    return dict(mu=mu, sd=sd, ref=z, dbar=dbar, thr=(nn / dbar).max())


def di(f, pts):
    z = (pts - f["mu"]) / f["sd"]
    return np.linalg.norm(z[:, None] - f["ref"][None], axis=-1).min(1) / f["dbar"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--data", nargs="+", required=True)
    a = ap.parse_args()
    f = fit(points(a.train))
    print(f"training points {len(f['ref'])}, AOA threshold (max training DI) {f['thr']:.2f}")
    for p in a.data:
        v = di(f, points(p))
        print(f"{p}: {len(v)} points, DI min {v.min():.2f} median {np.median(v):.2f} max {v.max():.2f}, "
              f"outside AOA {np.mean(v > f['thr']):.0%}")


if __name__ == "__main__":
    if __import__("sys").argv[1:]:
        main()
    else:  # self-check: a regular grid has DI 1 inside, 0 on its own points, and a far point is outside the AOA
        g = np.array([[la, lo, 1000.0, 1000.0 + 10 * la] for la in range(5) for lo in range(5)])
        f = fit(g)
        assert abs(f["thr"] - 1) < 1e-6 and di(f, g).max() == 0
        assert di(f, np.array([[2.5, 2.0, 1000, 1025.0]]))[0] < f["thr"] < di(f, np.array([[20.0, 2, 3000, 1200]]))[0]
        print("di self-check ok")
