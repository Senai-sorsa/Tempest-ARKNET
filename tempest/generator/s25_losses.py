"""New_Plan section 25 loss terms (GF1 b-d, GX2, GX1, MF1). Every term is off unless its train.py weight is set; with all of
them at their DEFAULTS train.py never imports this module's terms into the loss (tests/test_s25.py checks byte identity).

    es_beta              GF1b: energy-score exponent (1 = the shipped energy_score; the beta path is only taken when != 1)
    vario_weight, vario_p  GF1c: vertical variogram score per variable, pair weight 1 / separation (L3-13 / IL-47)
    shear_vec_es_weight  GF1d / IL-62: energy score on each layer's (du, dv) shear vector
    twes_weight, twes_q, twes_top_m, twes_tau  GX2: threshold-weighted energy score on the 0-twes_top_m (u, v) profile
    sig_weight, sig_stride GX1: energy score on depth-2 path signatures along height (every sig_stride-th height)
"""
import math

import numpy as np
import torch

from tempest.generator.model import energy_score
from tempest.profiles.to_heights import HEIGHTS, PROFILE


def _norm(x):
    return torch.sqrt(x.pow(2).sum(-1) + 1e-12)        # smooth at 0 (a plain norm has a NaN gradient for equal samples)


def energy_score_beta(samples, y, beta):
    """Energy score with exponent beta in (0, 2) (proper for every such beta): E|X - y|^b - 1/2 E|X - X'|^b, mean over the batch."""
    assert 0 < beta < 2, beta
    m = samples.shape[1]
    fit = _norm(samples - y.unsqueeze(1)).pow(beta).mean(1)
    spread = sum(_norm(samples[:, i] - samples[:, j]).pow(beta) for i in range(m) for j in range(i + 1, m))
    return (fit - spread / (m * (m - 1) / 2) / 2).mean()


def variogram_score(s, y, n_v, n_h, p=0.5):
    """Variogram score of order p (Scheuerer and Hamill 2015) along height, per variable, pair weight 1 / separation (normalised
    to sum 1). s (B, m, D), y (B, D): standardised profiles whose first n_v * n_h columns are the profiles. Mean over batch and variables."""
    B, m = s.shape[:2]
    sp = s[..., :n_v * n_h].reshape(B, m, n_v, n_h)
    yp = y[..., :n_v * n_h].reshape(B, n_v, n_h)
    i, j = torch.triu_indices(n_h, n_h, 1, device=s.device)
    w = 1.0 / (j - i).float()
    w = w / w.sum()
    pw = lambda d: (d.pow(2) + 1e-8).pow(p / 2)        # |d|^p with a finite gradient at 0
    ds = pw(sp[..., i] - sp[..., j]).mean(1)           # (B, n_v, P) ensemble mean of |X_i - X_j|^p
    dy = pw(yp[..., i] - yp[..., j])
    return ((dy - ds).pow(2) * w).sum(-1).mean()


def shear_vec_es(du_s, dv_s, du_y, dv_y):
    """IL-62: energy score of each layer's 2-D shear vector, mean over layers and batch. du_s (B, m, L), du_y (B, L), already scaled."""
    B, m, L = du_s.shape
    x = torch.stack([du_s, dv_s], -1).permute(0, 2, 1, 3).reshape(B * L, m, 2)
    return energy_score_beta(x, torch.stack([du_y, dv_y], -1).reshape(B * L, 2), 1.0)


def twes(xs, xy, ms, my, thr, tau):
    """GX2: threshold-weighted energy score (Allen et al. 2023) with chaining function v(x) = x * sigmoid((maxshear(x) - thr) / tau).
    xs (B, m, K) standardised (u, v) profile samples, xy (B, K) truth, ms (B, m) / my (B,) their max shear. Proper because v is a fixed map."""
    vs = xs * torch.sigmoid((ms - thr) / tau).unsqueeze(-1)
    vy = xy * torch.sigmoid((my - thr) / tau).unsqueeze(-1)
    return energy_score_beta(vs, vy, 1.0) / math.sqrt(xs.shape[-1])


def signature2(path):
    """Depth-2 truncated signature of a piecewise-linear path. path (..., N, c) -> (..., c + c*c): level 1 = total increment,
    level 2 = sum_k (x_{k-1} - x_0) (x) dx_k + 1/2 dx_k (x) dx_k.
    shortcut: depth-2 truncation scored with an energy score, not the full signature-kernel PDE score of arXiv 2510.19110; upgrade if GX1 moves shape."""
    dx = path[..., 1:, :] - path[..., :-1, :]
    rel = path[..., :-1, :] - path[..., :1, :]
    s1 = path[..., -1, :] - path[..., 0, :]
    s2 = torch.einsum("...ka,...kb->...ab", rel, dx) + 0.5 * torch.einsum("...ka,...kb->...ab", dx, dx)
    return torch.cat([s1, s2.flatten(-2)], -1)


def energy_distance(s, t):
    """MF1: energy distance between student samples s (B, m, D) and teacher samples t (B, k, D), without the constant teacher-teacher term:
    E|S - T| - 1/2 E|S - S'|, mean over the batch."""
    m = s.shape[1]
    cross = _norm(s.unsqueeze(2) - t.unsqueeze(1)).mean((1, 2))
    spread = sum(_norm(s[:, i] - s[:, j]) for i in range(m) for j in range(i + 1, m)) / (m * (m - 1) / 2)
    return (cross - spread / 2).mean()


def make_terms(cfg, tref, norm, device):
    """-> fn(samples, t, s, y) adding every switched-on term, or None. tref: raw training target sample (N, D) in difference space;
    norm: train.py's cm / cs / tm / ts. samples / t are normalised differences, s / y standardised profiles (as in train.score)."""
    n_h, n_v = len(HEIGHTS), len(PROFILE)
    n_prof = n_h * n_v
    iu, iv = PROFILE.index("u"), PROFILE.index("v")
    tm_d, ts_d = norm["tm"].to(device), norm["ts"].to(device)
    dz = np.diff(HEIGHTS) / 1000.0
    dref = tref[:, :n_prof].reshape(len(tref), n_v, n_h)[..., 1:]
    out = []

    def diffs(x):                                       # normalised diffs -> raw layer steps (..., n_v, n_h - 1)
        return (x[..., :n_prof] * ts_d[:n_prof] + tm_d[:n_prof]).reshape(*x.shape[:-1], n_v, n_h)[..., 1:]

    if cfg.get("vario_weight"):
        w, p = float(cfg["vario_weight"]), float(cfg.get("vario_p", 0.5))
        out.append(lambda samples, t, s, y: w * variogram_score(s, y, n_v, n_h, p))
    if cfg.get("shear_vec_es_weight"):
        w = float(cfg["shear_vec_es_weight"])
        sc = torch.tensor(np.sqrt((dref[:, iu].std(0) ** 2 + dref[:, iv].std(0) ** 2) / 2) + 1e-6, dtype=torch.float32, device=device)

        def sv(samples, t, s, y):
            a, b = diffs(samples), diffs(t)
            return w * shear_vec_es(a[..., iu, :] / sc, a[..., iv, :] / sc, b[..., iu, :] / sc, b[..., iv, :] / sc)
        out.append(sv)
    if cfg.get("twes_weight"):
        w = float(cfg["twes_weight"])
        top = np.flatnonzero(np.asarray(HEIGHTS) <= float(cfg.get("twes_top_m", 18000.0)))
        lay = top[1:] - 1                               # layers fully inside 0-top
        mref = (np.hypot(dref[:, iu], dref[:, iv]) / dz)[:, lay].max(1)
        thr = float(np.quantile(mref, float(cfg.get("twes_q", 0.9))))
        tau = float(cfg.get("twes_tau", 0.1)) * thr
        cols = torch.tensor(np.concatenate([iu * n_h + top, iv * n_h + top]), device=device)
        lay_t, dz_t = torch.tensor(lay, device=device), torch.tensor(dz, dtype=torch.float32, device=device)

        def maxshear(x):
            d = diffs(x)
            return (torch.hypot(d[..., iu, :], d[..., iv, :]) / dz_t)[..., lay_t].amax(-1)

        out.append(lambda samples, t, s, y: w * twes(s[..., cols], y[..., cols], maxshear(samples), maxshear(t), thr, tau))
    if cfg.get("sig_weight"):
        w, st = float(cfg["sig_weight"]), int(cfg.get("sig_stride", 1))
        hz = torch.tensor(np.asarray(HEIGHTS, float)[::st] / float(HEIGHTS[-1]), dtype=torch.float32, device=device)

        def sig(samples, t, s, y):
            def path(x):                                # (..., D) -> (..., N, n_v + 1): the 4 standardised profiles plus height as the time channel
                p = x[..., :n_prof].reshape(*x.shape[:-1], n_v, n_h)[..., ::st].transpose(-1, -2)
                return torch.cat([p, hz.view(*([1] * (p.dim() - 2)), -1, 1).expand(*p.shape[:-1], 1)], -1)
            fs, fy = signature2(path(s)), signature2(path(y))
            return w * energy_score_beta(fs, fy, 1.0) / math.sqrt(fs.shape[-1])
        out.append(sig)
    if not out:
        return None
    return lambda samples, t, s, y: sum(f(samples, t, s, y) for f in out)
