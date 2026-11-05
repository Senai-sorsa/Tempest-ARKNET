"""Numerics copied from the main package so this folder stands alone (numpy only). A parity test in the main repo
(tests/test_tool_parity.py) compares every function here with its original; change both together.
"""
import numpy as np

HEIGHTS = np.array([10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000] + list(range(2500, 18001, 500)), dtype=np.float32)
PROFILE = ["u", "v", "T", "RH"]
SURFACE = ["t2m", "sp", "rh2m"]
NH = len(HEIGHTS)
RD, RV, G0, R_EARTH, GAMMA = 287.05, 461.5, 9.80665, 6371000.0, 1.4
EPS = RD / RV


def from_diff(d):
    return np.cumsum(d, axis=-1)


def standard_pressure(z):
    return 101325.0 * (1 - 2.25577e-5 * np.asarray(z, np.float64)) ** 5.25588


def es_liquid(t):
    return 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))


def rh_from_dpd(t, lnd):
    td = t - np.maximum(np.expm1(np.clip(lnd, None, 5.0)), 0.0)
    return 100.0 * es_liquid(td) / es_liquid(t)


def clip_ranges(phys):
    i = PROFILE.index("RH") * NH
    phys[..., i:i + NH] = np.clip(phys[..., i:i + NH], 0, 100)
    phys[..., NH * len(PROFILE) + SURFACE.index("rh2m")] = np.clip(phys[..., NH * len(PROFILE) + SURFACE.index("rh2m")], 0, 100)
    return phys


def to_physical(raw, rh_target="rh"):
    """(..., 179) raw targets (surface value + neighbour differences, then t2m, sp, rh2m) -> physical values."""
    n, p = NH, len(PROFILE)
    prof = from_diff(raw[..., :n * p].reshape(*raw.shape[:-1], p, n))
    rest = raw[..., n * p:]
    if rh_target == "dpd":
        prof = np.array(prof, dtype=np.float64)
        prof[..., PROFILE.index("RH"), :] = rh_from_dpd(prof[..., PROFILE.index("T"), :], prof[..., PROFILE.index("RH"), :])
        rest = np.array(rest, dtype=np.float64)
        rest[..., SURFACE.index("rh2m")] = rh_from_dpd(rest[..., SURFACE.index("t2m")], rest[..., SURFACE.index("rh2m")])
        prof, rest = prof.astype(raw.dtype), rest.astype(raw.dtype)
    return clip_ranges(np.concatenate([prof.reshape(*raw.shape[:-1], n * p), rest], axis=-1))


def _standardise(x):
    lo, med, hi = np.quantile(x, [0.05, 0.5, 0.95], axis=1, keepdims=True)
    hw = (hi - lo) / 2
    hw = np.maximum(hw, 0.1 * np.median(hw, axis=0, keepdims=True) + 1e-6)
    return (x - med) / hw, med, hw


def calibrate(table, samples, clip=True):
    """Range calibration (per-column quantile map). samples (N, m, D) with m equal to the m the table was fitted with."""
    if "m" in table and int(table["m"]) != samples.shape[1]:
        raise ValueError(f"calibration fitted with m = {int(table['m'])}, applied to m = {samples.shape[1]}")
    z, med, hw = _standardise(samples.astype(np.float64))
    qz, qu = table["qz"], table["qu"]
    out = np.empty_like(z)
    for j in range(z.shape[-1]):
        a, b, zj = qz[:, j], qu[:, j], z[..., j]
        a = np.maximum.accumulate(a + np.arange(len(a)) * 1e-9)
        y = np.interp(zj, a, b)
        lo_s = (b[4] - b[0]) / max(a[4] - a[0], 1e-9)
        hi_s = (b[-1] - b[-5]) / max(a[-1] - a[-5], 1e-9)
        y = np.where(zj < a[0], b[0] + (zj - a[0]) * lo_s, y)
        out[..., j] = np.where(zj > a[-1], b[-1] + (zj - a[-1]) * hi_s, y)
    res = (med + out * hw).astype(samples.dtype)
    return clip_ranges(res) if clip else res


def gravity(z_asl):
    return G0 * (R_EARTH / (R_EARTH + z_asl)) ** 2


def mixing_q(t, rh, p):
    e = np.clip(rh, 0, 100) / 100.0 * es_liquid(t)
    return EPS * e / (p - (1 - EPS) * e)


def thermo_column(z_agl, T, rh, ps, t_sfc=None, rh_sfc=None, z_sfc=0.0):
    """p (Pa), rho (kg/m3), a (m/s), q, tv along a profile by hypsometric integration (see tempest.profiles.thermo)."""
    z_agl = np.asarray(z_agl, np.float64)
    T, rh, ps = (np.asarray(x, np.float64) for x in (T, rh, ps))
    t0 = T[..., 0] if t_sfc is None else np.asarray(t_sfc, np.float64)
    r0 = rh[..., 0] if rh_sfc is None else np.asarray(rh_sfc, np.float64)
    zs = np.asarray(z_sfc, np.float64)
    z_edges = np.concatenate([[0.0], z_agl])
    dz = np.diff(z_edges)
    g = gravity(zs[..., None] + 0.5 * (z_edges[1:] + z_edges[:-1]))
    t_all = np.concatenate([t0[..., None], T], -1)
    r_all = np.concatenate([r0[..., None], rh], -1)
    tv = t_all
    for _ in range(2):
        inc = g * dz / (RD * 0.5 * (tv[..., 1:] + tv[..., :-1]))
        p_all = ps[..., None] * np.exp(-np.concatenate([np.zeros_like(inc[..., :1]), np.cumsum(inc, -1)], -1))
        q_all = mixing_q(t_all, r_all, p_all)
        tv = t_all * (1 + (RV / RD - 1) * q_all)
    p, q, tvl = p_all[..., 1:], q_all[..., 1:], tv[..., 1:]
    return dict(p=p, rho=p / (RD * tvl), a=np.sqrt(GAMMA * RD * tvl), q=q, tv=tvl)


def feature_matrix(names, lat, lon, elev_site, elev_grid, doy, solar_hour, year, oni, wwv, qbo30, qbo50, gmst=None, oni_lag3=None):
    """Inputs in the order the model was trained with (`names` comes from the exported model)."""
    a = 2 * np.pi * np.asarray(doy, float) / 365.25
    h = 2 * np.pi * np.asarray(solar_hour, float) / 24.0
    oni = np.asarray(oni, float)
    cols = dict(lat=lat, lon=lon, elev_site=elev_site, elev_grid=elev_grid, doy_sin=np.sin(a), doy_cos=np.cos(a), hour_sin=np.sin(h),
                hour_cos=np.cos(h), year=year, oni=oni, wwv=wwv, qbo30=qbo30, qbo50=qbo50, oni_pos=np.maximum(oni, 0), oni_neg=np.minimum(oni, 0))
    if gmst is not None:
        cols["gmst"] = gmst
    if oni_lag3 is not None:
        cols["oni_lag3"] = oni_lag3
    missing = [k for k in names if k not in cols]
    if missing:
        raise ValueError(f"model needs inputs {missing} that were not supplied")
    return np.stack(np.broadcast_arrays(*[np.asarray(cols[k], float) for k in names]), axis=-1).astype(np.float32)


LAPSE, SHIFT_SCALE = 0.0065, 1500.0


def site_shift(phys, dz):
    """(n, 179) values at the grid elevation -> the site elevation `dz` metres higher (in place; dz a number or one value per row): sp hypsometric, t2m with the standard
    lapse rate, the temperature profile with a shift that fades with height (-lapse * dz * exp(-z / 1500 m): no jump between 2 m and 10 m), humidity keeping its dew point
    where the shift acts."""
    nh = NH
    dz = np.broadcast_to(np.asarray(dz, np.float64), (len(phys),))
    d2 = dz[:, None]
    t = phys[:, 4 * nh].astype(np.float64)
    phys[:, 4 * nh + 1] *= np.exp(-G0 * dz / (RD * (t - LAPSE * dz / 2)))
    w = np.exp(-HEIGHTS / SHIFT_SCALE)
    t_old = phys[:, 2 * nh:3 * nh].astype(np.float64)
    t_new = t_old - LAPSE * d2 * w
    rh = phys[:, 3 * nh:4 * nh]
    phys[:, 3 * nh:4 * nh] = np.clip(rh * es_liquid(t_old) / es_liquid(t_new) * w + rh * (1 - w), 0, 100)
    phys[:, 2 * nh:3 * nh] = t_new
    phys[:, 4 * nh + 2] = np.clip(phys[:, 4 * nh + 2] * es_liquid(t) / es_liquid(t - LAPSE * dz), 0, 100)
    phys[:, 4 * nh] = t - LAPSE * dz
    return phys


def bilinear(grid_lat, grid_lon, lat, lon):
    """The (up to) four grid points around (lat, lon) and their bilinear weights -> (point indices (k,), weights (k,)); a query on a grid point gives that point alone."""
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
    """Whole blocks per point in proportion to the weights (largest remainder, ties by chance): [counts] summing to `blocks`."""
    exact = np.asarray(weights) * blocks
    c = np.floor(exact).astype(int)
    rest = blocks - c.sum()
    if rest:
        order = np.argsort(-(exact - c) + 1e-9 * rng.random(len(c)))
        c[order[:rest]] += 1
    return c
