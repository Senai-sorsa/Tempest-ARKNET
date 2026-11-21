"""Numpy forward pass of the exported Engression networks (generator and vertical-wind head). No torch.

    net = Net.load(npz_path)             # a model exported by tempest/export_tool.py
    raw = net.sample(cond, rng=rng)      # (N, n_out) raw targets, rows spread over the members

The architecture is tempest/generator/model.py: noise embedding -> input layer -> residual blocks whose layer norm is shifted and scaled
by the embedding -> head; inputs flagged `linear_cols` bypass the blocks and enter as straight-line effects. `eps` can be passed in for
tests so a torch run and this run see identical noise.
"""
import json

import numpy as np

from tempest_weather import _core

LN_EPS = 1e-5


def _ln(x, w=None, b=None):
    mu = x.mean(-1, keepdims=True)
    y = (x - mu) / np.sqrt(x.var(-1, keepdims=True) + LN_EPS)
    return y if w is None else y * w + b


def _silu(x):
    return x / (1 + np.exp(-x))


X4R_COLS = ["lat", "lon", "doy_sin", "doy_cos", "hour_sin", "hour_cos"]   # = tempest.generator.model.ANOM_COLS (the tool does not import torch code)


class Member:
    def __init__(self, w, norm, meta):
        self.w, self.norm = w, norm
        self.keep = [i for i in range(meta["n_cond"]) if i not in meta["linear_cols"]]
        self.lin = list(meta["linear_cols"])
        self.noise_dim = meta["noise_dim"]
        self.depth = meta["depth"]

    def forward(self, cond_n, eps):
        """cond_n (B, F) normalised, eps (B, noise_dim) -> (B, n_out) normalised (one sample per row)."""
        w = self.w
        x = cond_n[:, self.lin] if self.lin else None
        c = cond_n[:, self.keep]
        z = _ln(_silu(eps @ w["embed.0.weight"].T + w["embed.0.bias"]) @ w["embed.2.weight"].T + w["embed.2.bias"], w["embed.3.weight"], w["embed.3.bias"])
        h = np.concatenate([c, eps], -1) @ w["inp.weight"].T + w["inp.bias"]
        for k in range(self.depth):
            s, b = np.split(z @ w[f"blocks.{k}.film.weight"].T + w[f"blocks.{k}.film.bias"], 2, axis=-1)
            f = _ln(h) * (1 + s) + b
            f = _silu(f @ w[f"blocks.{k}.ff.0.weight"].T + w[f"blocks.{k}.ff.0.bias"]) @ w[f"blocks.{k}.ff.2.weight"].T + w[f"blocks.{k}.ff.2.bias"]
            h = h + f
        out = _ln(h, w["head.0.weight"], w["head.0.bias"]) @ w["head.1.weight"].T + w["head.1.bias"]
        if self.lin:
            s = (_silu(c @ w["slope.0.weight"].T + w["slope.0.bias"]) @ w["slope.2.weight"].T + w["slope.2.bias"]).reshape(len(c), len(self.lin), -1)
            out = out + np.einsum("bk,bkd->bd", x, s)
        return out


class Net:
    def __init__(self, members, meta):
        self.members, self.meta = members, meta
        self.names = meta["cond_names"]

    @classmethod
    def load(cls, path, prefix=""):
        z = np.load(path, allow_pickle=False)
        meta = json.loads(str(z[prefix + "meta"]))
        members = []
        for k in range(meta["members"]):
            w = {n.split("/", 1)[1]: z[n] for n in z.files if n.startswith(f"{prefix}m{k}/")}
            norm = {n: z[f"{prefix}norm{k}/{n}"].astype(np.float32) for n in ("cm", "cs", "tm", "ts")}
            members.append(Member({a: b.astype(np.float32) for a, b in w.items()}, norm, meta))
        net = cls(members, meta)
        if meta.get("x4r"):                                             # New_Plan 28.11: X4-R climatology offset table (keys (P, 2), dc (P, 11, n_out))
            net.x4r = dict(keys=z[prefix + "x4r/keys"].astype(np.float64), dc=z[prefix + "x4r/dc"].astype(np.float64))
        return net

    def x4r_offset(self, cond):
        """X4-R: raw-target offset per row (N, n_out): harmonic fit at the nearest table point (cos-lat distance, as the torch model),
        0 for rows farther than meta x4r_cutoff degrees from every table point (outside the fitted area the offset is unknown)."""
        t, cols = self.x4r, [self.names.index(c) for c in X4R_COLS]
        c = np.asarray(cond, np.float64)[:, cols]
        k = t["keys"]
        d = (c[:, :1] - k[:, 0]) ** 2 + ((c[:, 1:2] - k[:, 1]) * np.cos(np.deg2rad(c[:, :1]))) ** 2
        p = d.argmin(1)
        a, b = np.arctan2(c[:, 2], c[:, 3]), np.arctan2(c[:, 4], c[:, 5])
        X = np.stack([np.ones_like(a)] + [f(j * a) for j in (1, 2, 3) for f in (np.sin, np.cos)] + [f(j * b) for j in (1, 2) for f in (np.sin, np.cos)], -1)
        off = np.einsum("bk,bkd->bd", X, t["dc"][p])
        off[np.sqrt(d[np.arange(len(p)), p]) > self.meta["x4r_cutoff"]] = 0.0
        return off.astype(np.float32)

    def sample(self, cond, rng=None, eps=None):
        """cond (N, F) raw features, one row per sample -> (N, n_out) raw targets. Row i goes to member i % K, as in tempest.generator.sample.Sampler."""
        cond = np.asarray(cond, np.float32)
        rng = rng or np.random.default_rng()
        K = len(self.members)
        out = np.empty((len(cond), self.meta["n_out"]), np.float32)
        for i, m in enumerate(self.members):
            c = cond[i::K]
            e = rng.standard_normal((len(c), self.meta["noise_dim"])).astype(np.float32) if eps is None else eps[i::K]
            out[i::K] = m.forward((c - m.norm["cm"]) / m.norm["cs"], e) * m.norm["ts"] + m.norm["tm"]
        if getattr(self, "x4r", None) is not None:
            out += self.x4r_offset(cond)
        so = self.meta.get("sp_offset")
        if so is not None:
            out[:, so[0]] += _core.standard_pressure(cond[:, so[1]]).astype(np.float32)
        return out

    def profiles(self, cond, rng=None, eps=None):
        """Physical samples (N, 179) with the humidity rule and range limits applied."""
        return _core.to_physical(self.sample(cond, rng, eps), self.meta.get("rh_target", "rh"))


# ---- New_Plan section 25 (GF3 flow, MF2 RML): numpy samplers for the multi-step generators. Not used by any shipped model.

def tau_embed(tau, dim):
    """Numpy twin of tempest.generator.s25_models.tau_embed (flow time -> the inner net's noise input)."""
    f = np.exp(np.linspace(0.0, np.log(1000.0), dim // 2)).astype(np.float32)
    a = np.asarray(tau, np.float32)[:, None] * f
    return (np.concatenate([np.sin(a), np.cos(a)], -1) * np.sqrt(2.0)).astype(np.float32)


def inner_member(state, norm, meta, prefix="net."):
    """Torch state dict of a flow / rml checkpoint (numpy arrays or tensors) -> the inner Engression network as a Member.
    meta: n_cond (of the inner net: features + n_out [+ K]), linear_cols, noise_dim, depth."""
    w = {k[len(prefix):]: np.asarray(v, np.float32) for k, v in state.items() if k.startswith(prefix)}
    return Member(w, norm, meta)


def flow_sample(inner, cond_n, steps, rng, tau0=0.0, x=None):
    """Euler integration of a rectified flow: cond_n (N, F) normalised -> (N, n_out) normalised. Cost = `steps` forward passes."""
    n_out = len(inner.norm["tm"])
    x = rng.standard_normal((len(cond_n), n_out)).astype(np.float32) if x is None else x
    dt = (1.0 - tau0) / steps
    for k in range(steps):
        e = tau_embed(np.full(len(cond_n), tau0 + k * dt, np.float32), inner.noise_dim)
        x = x + dt * inner.forward(np.concatenate([cond_n, x], -1), e)
    return x


def rml_sample(inner, cond_n, K, rng):
    """Reverse Markov Learning chain: K Engression steps from pure noise; cost = K forward passes."""
    n_out = len(inner.norm["tm"])
    x = rng.standard_normal((len(cond_n), n_out)).astype(np.float32)
    for k in range(K, 0, -1):
        oh = np.zeros((len(cond_n), K), np.float32)
        oh[:, k - 1] = 1
        e = rng.standard_normal((len(cond_n), inner.noise_dim)).astype(np.float32)
        x = inner.forward(np.concatenate([cond_n, x, oh], -1), e)
    return x
