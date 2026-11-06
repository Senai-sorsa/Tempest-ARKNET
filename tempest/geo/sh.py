"""Real spherical harmonics up to degree L as a location encoding (no seam at the date line, no pole singularity).

sh(lat_deg, lon_deg, L) -> (..., (L + 1)**2), 4-pi normalised: the mean of Y_i * Y_j over the sphere is delta_ij.
Works on numpy arrays and torch tensors (same code path). Fully normalised associated Legendre recursion.
"""
import math


def sh(lat, lon, L: int):
    xp = _ns(lat)
    t = lat * (math.pi / 180)
    lam = lon * (math.pi / 180)
    c, s = xp.sin(t), xp.cos(t)             # cos(colatitude), sin(colatitude)
    P = {(0, 0): c * 0 + 1}
    for m in range(1, L + 1):              # diagonal
        P[m, m] = (math.sqrt(3) if m == 1 else math.sqrt((2 * m + 1) / (2 * m))) * s * P[m - 1, m - 1]
    for m in range(0, L):                  # first off-diagonal
        P[m + 1, m] = math.sqrt(2 * m + 3) * c * P[m, m]
    for m in range(0, L + 1):
        for l in range(m + 2, L + 1):
            a = math.sqrt((4 * l * l - 1) / (l * l - m * m))
            b = math.sqrt(((l - 1) ** 2 - m * m) / (4 * (l - 1) ** 2 - 1))
            P[l, m] = a * (c * P[l - 1, m] - b * P[l - 2, m])
    out = []
    for l in range(L + 1):
        out.append(P[l, 0])
        for m in range(1, l + 1):
            out.append(P[l, m] * xp.cos(m * lam))   # geodesy 4-pi normalisation: the factor 2 for m > 0 is already in P[m, m]
            out.append(P[l, m] * xp.sin(m * lam))
    return xp.stack(out, -1)


def _ns(x):
    if type(x).__module__.startswith("torch"):
        import torch
        return torch
    import numpy
    return numpy
