"""Coupled atmosphere files (Code-Modifications/coupled-atmosphere.md, Part 1).

    from tempest.output.coupled import build, write
    arrays, meta = build(phys, elev_site, drivers, query=dict(...), member=member)   # phys (n, 179) physical samples
    write("out_dir", arrays, meta)       # atmosphere_samples.npz, atmosphere_coupling.npz, atmosphere_coupling.toml

The rule: one row is one whole atmosphere. Every quantity of a Monte Carlo run comes from the same row k; nothing is
dispersed on its own. p, rho and a are derived from the row's own T, RH and surface pressure (profiles.thermo), so they
are consistent with it. Vertical wind, thermals, gust parameters and the soak history are NaN placeholders until
Phase 3 fills them in. Correlations, EOFs and shear statistics are computed from the samples for checking only:
new atmospheres must never be rebuilt from them.
"""
import hashlib
import json
import os

import numpy as np

from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS, PROFILE

GUST_HEIGHTS = HEIGHTS[HEIGHTS <= 200]
COUPLED_VARS = ["u", "v", "T", "p", "rho", "a", "RH", "w"]  # w joins the correlations once it is filled in (finite)
QUANTILES = [50, 90, 99, 99.9]
SOAK_HOURS = 24


def build(phys, elev_site, drivers, query=None, member=None, weight=None, stratum_top_m=3000.0, extras=None):
    """phys (n, 179) physical samples (to_physical output), drivers (n, 5) = oni, wwv, qbo30, qbo50, warming ->
    (arrays, meta). Samples keep their row order."""
    phys = np.asarray(phys, np.float64)
    n, nh = len(phys), len(HEIGHTS)
    u, v, T, RH = (phys[:, i * nh:(i + 1) * nh] for i in range(len(PROFILE)))
    t2m, sp, rh2m = (phys[:, len(PROFILE) * nh + j] for j in range(3))
    th = thermo.column(HEIGHTS, T, RH, sp, t_sfc=t2m, rh_sfc=rh2m, z_sfc=elev_site)
    nan = lambda *s: np.full(s, np.nan, np.float32)
    speed = np.hypot(u, v)[:, HEIGHTS <= stratum_top_m].mean(1)
    arrays = dict(
        height_agl=HEIGHTS.astype(np.float32), height_asl=(elev_site + HEIGHTS).astype(np.float32),
        u=u.astype(np.float32), v=v.astype(np.float32), w=nan(n, nh), T=T.astype(np.float32),
        p=th["p"].astype(np.float32), rho=th["rho"].astype(np.float32), a=th["a"].astype(np.float32),
        RH=RH.astype(np.float32), w_sigma=nan(n, nh), w_turb=nan(n, nh),
        t2m=t2m.astype(np.float32), sp=sp.astype(np.float32), rh2m=rh2m.astype(np.float32),
        gust_mu=nan(n, len(GUST_HEIGHTS)), gust_beta=nan(n, len(GUST_HEIGHTS)), gust_heights=GUST_HEIGHTS.astype(np.float32),
        soak_t2m=nan(n, SOAK_HOURS), soak_ssrd=nan(n, SOAK_HOURS), soak_wind10=nan(n, SOAK_HOURS), T_soak=nan(n),
        weight=np.ones(n, np.float32) if weight is None else np.asarray(weight, np.float32),
        member=np.zeros(n, np.int16) if member is None else np.asarray(member, np.int16),
        drivers=np.asarray(drivers, np.float32), stratum_key=speed.astype(np.float32))
    # Phase 3 outputs, row for row from the same samples: w (n, 44), w_sigma, w_turb (n, 44), gust_mu, gust_beta (n, g),
    # soak_t2m, soak_ssrd, soak_wind10 (n, 24), T_soak (n,). Anything not given stays NaN (a placeholder).
    for k, v in (extras or {}).items():
        if k not in arrays or np.shape(v) != arrays[k].shape:
            raise ValueError(f"extras[{k!r}] must match the shape {arrays.get(k, np.empty(0)).shape if k in arrays else 'of an existing key'}")
        arrays[k] = np.asarray(v, np.float32)
    placeholders = [k for k in ("w", "w_sigma", "w_turb", "gust_mu", "gust_beta", "soak_t2m", "soak_ssrd", "soak_wind10", "T_soak")
                    if np.isnan(arrays[k]).all()]
    meta = dict(coupling="whole-sample", n=int(n), site_elevation_m=float(elev_site), stratum="mean wind speed 0-3 km AGL",
                placeholders=placeholders, query=query or {}, tau_soak_hours=None)
    return arrays, meta


def _corr(x, spearman=False):
    """Correlation of columns of x (n, d); constant columns give 0 off the diagonal and 1 on it."""
    if spearman:
        x = np.argsort(np.argsort(x, axis=0), axis=0).astype(np.float64)
    x = x - x.mean(0)
    sd = x.std(0)
    ok = sd > 1e-12
    z = np.where(ok, x / np.where(ok, sd, 1), 0.0)
    c = z.T @ z / len(x)
    c[~ok, :] = 0
    c[:, ~ok] = 0
    c[np.diag_indices_from(c)] = 1.0
    return c


def coupling(arrays, variance=0.99):
    """Correlation / EOF / shear summaries computed from the samples (n rows)."""
    nh = len(HEIGHTS)
    vs = [k for k in COUPLED_VARS if np.isfinite(arrays[k]).all()]
    prof = np.stack([arrays[k].astype(np.float64) for k in vs], 1)             # (n, V, 44)
    n, V = prof.shape[0], len(vs)
    out = dict(variables=np.array(vs))
    for tag, sp_ in (("corr", False), ("spearman", True)):
        out[f"{tag}_vars_at_height"] = np.stack([_corr(prof[:, :, h], sp_) for h in range(nh)])        # (44, V, V)
        for i, k in enumerate(vs):
            out[f"{tag}_heights_{k}"] = _corr(prof[:, i, :], sp_)                                        # (44, 44)
        full = prof.reshape(n, V * nh)
        out[f"{tag}_full"] = _corr(full, sp_)
        sfc = [k for k in ("t2m", "sp", "rh2m", "gust_mu", "T_soak") if np.isfinite(arrays[k]).all()]
        s = np.stack([arrays[k].astype(np.float64) if arrays[k].ndim == 1 else arrays[k][:, 0].astype(np.float64) for k in sfc], 1)
        out[f"{tag}_surface"] = _corr(np.concatenate([s, full], 1), sp_)[:len(sfc), len(sfc):]            # (S, V*44)
        out[f"{tag}_surface_names"] = np.array(sfc)
    full = prof.reshape(n, V * nh)
    sd = full.std(0)
    z = (full - full.mean(0)) / np.where(sd > 1e-12, sd, 1)
    _, sv, vt = np.linalg.svd(z, full_matrices=False)
    share = sv ** 2 / (sv ** 2).sum()
    k = int(np.searchsorted(np.cumsum(share), variance) + 1)
    out.update(eof_modes=vt[:k].astype(np.float32), eof_variance=share[:k].astype(np.float32),
               eof_scores=(z @ vt[:k].T).astype(np.float32))
    steps = {k_: np.abs(np.diff(arrays[k_].astype(np.float64), axis=1)) for k_ in vs}
    out["shear_stats"] = np.array([[np.percentile(steps[k_], q) for q in QUANTILES] for k_ in vs])
    out["shear_quantiles"] = np.array(QUANTILES)
    return out


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(out_dir, arrays, meta):
    """-> dict of written paths. The TOML repeats the key correlations, the file name, n and the samples' sha256."""
    os.makedirs(out_dir, exist_ok=True)
    sp_ = os.path.join(out_dir, "atmosphere_samples.npz")
    cp_ = os.path.join(out_dir, "atmosphere_coupling.npz")
    np.savez(sp_, **arrays, metadata=json.dumps(meta))
    c = coupling(arrays)
    np.savez(cp_, **c)
    vs = list(c["variables"])
    zi = lambda m: int(np.argmin(np.abs(HEIGHTS - m)))
    uu = c["corr_heights_u"][zi(1000), zi(10000)]
    tr = {b: float(np.mean([c["corr_vars_at_height"][h, vs.index("T"), vs.index("rho")] for h in range(len(HEIGHTS))
                            if lo <= HEIGHTS[h] < hi])) for b, (lo, hi) in
          {"0-1km": (0, 1000), "1-5km": (1000, 5000), "5-12km": (5000, 12000), "12-18km": (12000, 18001)}.items()}
    toml = ["# Coupling summary computed from the samples, for checking only. Do NOT rebuild atmospheres from it:",
            "# sampling mean/std or correlations loses the skewed shapes and the extremes. Draw whole samples.",
            "display_only = true  # applies to every mean/std table written next to this file", "",
            "[coupling]", 'rule = "whole-sample"', f'samples_file = "atmosphere_samples.npz"', f"n = {meta['n']}",
            f'samples_sha256 = "{_sha(sp_)}"', f"u_1km_vs_10km = {uu:.4f}", "", "[coupling.T_vs_rho]"]
    toml += [f"{b} = {x:.4f}" for b, x in tr.items()]
    toml += ["", "[coupling.eof]", f"modes_for_99pct = {len(c['eof_variance'])}",
             "variance_first_3 = [" + ", ".join(f"{x:.4f}" for x in c["eof_variance"][:3]) + "]"]
    tp = os.path.join(out_dir, "atmosphere_coupling.toml")
    with open(tp, "w", encoding="utf-8") as f:
        f.write("\n".join(toml) + "\n")
    return dict(samples=sp_, coupling=cp_, toml=tp)
