"""Bilinear blending over the 0.25 degree grid (review item F-6): the four grid points around a query and how many whole range-map blocks each one gets.
Same functions as tempest_weather._core (the standalone tool keeps its own copy)."""
import numpy as np


def bilinear(grid_lat, grid_lon, lat, lon):
    """-> (point indices (k,), weights (k,)) of the up to four grid points around (lat, lon); a query on a grid point gives that point alone."""
    ulat, ulon = np.unique(np.round(grid_lat, 4)), np.unique(np.round(grid_lon, 4))
    index = {(round(float(a), 4), round(float(b), 4)): i for i, (a, b) in enumerate(zip(grid_lat, grid_lon))}

    def axis(u, x):
        j = int(np.clip(np.searchsorted(u, x, "right"), 1, len(u) - 1))
        f = float(np.clip((x - u[j - 1]) / (u[j] - u[j - 1]), 0.0, 1.0))
        return (u[j - 1], u[j]), (1.0 - f, f)
    (la0, la1), (wa0, wa1) = axis(ulat, lat)
    (lo0, lo1), (wo0, wo1) = axis(ulon, lon)
    pts, wts = [], []
    for la, wa in ((la0, wa0), (la1, wa1)):
        for lo, wo in ((lo0, wo0), (lo1, wo1)):
            if wa * wo > 1e-9:
                pts.append(index[(round(float(la), 4), round(float(lo), 4))])
                wts.append(wa * wo)
    w = np.array(wts)
    return np.array(pts), w / w.sum()


def allocate(weights, blocks, rng):
    """Whole blocks per point in proportion to the weights (largest remainder, ties by chance): counts summing to `blocks`."""
    exact = np.asarray(weights) * blocks
    c = np.floor(exact).astype(int)
    rest = blocks - c.sum()
    if rest:
        order = np.argsort(-(exact - c) + 1e-9 * rng.random(len(c)))
        c[order[:rest]] += 1
    return c
