"""New_Plan section 25 generator types. Reached only through model.make_generator with an arch other than "mlp" / "tokens", so the
shipped networks never import this file. Every model keeps the Generator call shape: forward(cond (B, F) normalised, m) -> (B, m, n_out)
normalised raw targets (differences), so tempest.generator.sample.Sampler, score.py and the calibration scripts work unchanged.

    flow    GF3 / H5: conditional rectified flow (velocity net = a Generator whose noise input carries the time embedding); Euler sampler
    rml     MF2: Reverse Markov Learning, a K-step chain of Engression steps from noise back to the profile (arXiv 2502.13747)
    har     GT1: height-autoregressive, the profile in `blocks` height blocks from the ground up, one shared network
    moe     H3: soft regime-gated expert heads on the shipped body (gate on the draft's 0-3 km lapse, 5.5 km wind, season)
    eof     H4: network for the top-k height EOFs + an AR(1)-in-height small scale with per-band amplitude / correlation length
    prior   H1: monthly statistical prior sample (AR(1) in height) as an extra input + learned correction; mode "noise" = the N(0,1) control
    analog  H2: k nearest training-period analogs (own year excluded) + learned per-band warp and a small correction
    refine  H5: a frozen one-step draft network + a flow trained only on the last part of the path (built by scripts/s25_compose_refine.py)

Arch options come from the training config's [s25] table (prepare() turns them into model_kw and fitted tables).
Tables (EOF basis, prior statistics, analog rows, profile scaling) are buffers, so they travel inside the checkpoint's state dict.
"""
import math

import numpy as np
import torch
from torch import nn

from tempest.generator.model import Generator, afcrps, energy_score
from tempest.profiles.to_heights import HEIGHTS, PROFILE

N_H, N_V = len(HEIGHTS), len(PROFILE)
N_PROF = N_H * N_V
BAND_EDGES = (1000.0, 3000.0, 10000.0)        # 4 height bands: 0-1, 1-3, 3-10, 10+ km (eof / analog)


def _ac(x):
    return torch.autocast(x.device.type, torch.bfloat16, enabled=x.is_cuda)


def tau_embed(tau, dim):
    """Flow time tau (N,) in [0, 1] -> (N, dim) sinusoidal embedding (numpy or torch, same numbers). It replaces the Generator's noise input."""
    assert dim % 2 == 0, "flow needs an even noise_dim (the time embedding is sin / cos pairs)"
    f = np.exp(np.linspace(0.0, math.log(1000.0), dim // 2))
    if isinstance(tau, torch.Tensor):
        a = tau.float()[:, None] * torch.as_tensor(f, dtype=torch.float32, device=tau.device)
        return torch.cat([torch.sin(a), torch.cos(a)], -1) * math.sqrt(2.0)
    a = np.asarray(tau, np.float32)[:, None] * f.astype(np.float32)
    return (np.concatenate([np.sin(a), np.cos(a)], -1) * math.sqrt(2.0)).astype(np.float32)


def band_of_heights():
    return np.searchsorted(np.asarray(BAND_EDGES), np.asarray(HEIGHTS, float), side="right")      # (N_H,) 0..3


class Space(nn.Module):
    """Normalised differences <-> standardised profiles (train.phys_std and its inverse). Buffers filled by set_tables."""

    def __init__(self, n_out):
        super().__init__()
        for k in ("tm", "ts", "pm", "ps"):
            self.register_buffer(k, torch.zeros(n_out))
        self.ts.fill_(1.0)
        self.ps.fill_(1.0)

    def to_std(self, x):
        r = x * self.ts + self.tm
        p = r[..., :N_PROF].reshape(*r.shape[:-1], N_V, N_H).cumsum(-1).reshape(*r.shape[:-1], N_PROF)
        return (torch.cat([p, r[..., N_PROF:]], -1) - self.pm) / self.ps

    def from_std(self, P):
        r = P * self.ps + self.pm
        p = r[..., :N_PROF].reshape(*r.shape[:-1], N_V, N_H)
        d = torch.cat([p[..., :1], p[..., 1:] - p[..., :-1]], -1).reshape(*r.shape[:-1], N_PROF)
        return (torch.cat([d, r[..., N_PROF:]], -1) - self.tm) / self.ts


class Tables(nn.Module):
    """Mixin: copy fitted arrays into same-named buffers (dotted names reach sub-modules)."""

    def set_tables(self, **t):
        for k, v in t.items():
            b = self.get_buffer(k)
            v = torch.as_tensor(np.asarray(v), dtype=b.dtype)
            assert tuple(v.shape) == tuple(b.shape), (k, tuple(v.shape), tuple(b.shape))
            b.copy_(v)


# ---------------------------------------------------------------- GF3 / H5: flow


class FlowGenerator(Tables):
    """Rectified flow: x_tau = (1 - tau) x0 + tau x1, x0 ~ N(0, I), x1 = normalised target; the net predicts v = x1 - x0 from (cond, x_tau, tau).
    flow = dict(steps=8 (Euler steps when sampling), train="fm" | "crps", train_steps=4 (differentiable steps for "crps", GF3 F2),
    tau_min=0.0 (H5: train only on tau in [tau_min, 1]; sampling then starts from tau_min, see RefineGenerator)).
    Flow-matching loss is the squared velocity error in standardised-profile space (train.phys_std is affine, so its offsets cancel)."""
    own_loss = True

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, flow=None, **gkw):
        super().__init__()
        self.flow = {**dict(steps=8, train="fm", train_steps=4, tau_min=0.0), **(flow or {})}
        self.n_out, self.noise_dim = n_out, noise_dim
        self.net = Generator(n_cond + n_out, n_out, noise_dim, width, depth, **gkw)

    def velocity(self, c, x, tau):
        return self.net(torch.cat([c, x], -1), 1, eps=tau_embed(tau, self.noise_dim).to(c.dtype))[:, 0]

    def integrate(self, c, x, tau0=None, steps=None):
        tau0 = self.flow["tau_min"] if tau0 is None else tau0
        steps = steps or self.flow["steps"]
        dt = (1.0 - tau0) / steps
        for k in range(steps):
            tau = torch.full((len(x),), tau0 + k * dt, device=x.device)
            x = x + dt * self.velocity(c, x, tau).to(x.dtype)
        return x

    def start(self, c, m):
        """(B*m) starting states at tau_min. Plain flow: noise only (tau_min > 0 without a draft is only used in training)."""
        return torch.randn(len(c), self.n_out, device=c.device)

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        c = cond.repeat_interleave(m, 0)
        return self.integrate(c, self.start(c, m)).view(B, m, -1)

    def train_loss(self, c, t, ctx):
        B = len(c)
        if self.flow["train"] == "crps":                 # GF3 F2: almost-fair CRPS + shipped terms on differentiable train_steps-step samples
            m = ctx["cfg"]["m"]
            cr = c.repeat_interleave(m, 0)
            with _ac(c):
                s = self.integrate(cr, torch.randn(B * m, self.n_out, device=c.device), 0.0, int(self.flow["train_steps"]))
            return ctx["score"](s.float().view(B, m, -1), t, ctx["top"])
        x0 = torch.randn_like(t)
        lo = float(self.flow["tau_min"])
        tau = lo + (1.0 - lo) * torch.rand(B, device=c.device)
        xt = (1 - tau)[:, None] * x0 + tau[:, None] * t
        with _ac(c):
            v = self.velocity(c, xt, tau)
        ps = ctx["phys_std"]
        return (ps(v.float()) - ps(t - x0)).pow(2).mean()


class RefineGenerator(Tables):
    """H5: draft = frozen one-step Engression network (the shipped kind); refinement = a FlowGenerator trained with tau_min = 1 - t0.
    Sampling: x = (1 - tau_min) eps + tau_min draft, then the flow's Euler steps from tau_min to 1. Built from two trained checkpoints
    by scripts/s25_compose_refine.py (not trained as one); refine = dict(draft=dict(noise_dim, width, depth, kw), flow=flow kwargs)."""

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, refine=None, linear_cols=None, **gkw):
        super().__init__()
        r = refine or {}
        dr = r.get("draft", {})
        self.n_out = n_out
        self.draft = Generator(n_cond, n_out, dr.get("noise_dim", noise_dim), dr.get("width", width), dr.get("depth", depth),
                               linear_cols=linear_cols, **dr.get("kw", {}))
        self.flow = FlowGenerator(n_cond, n_out, noise_dim, width, depth, flow=r.get("flow"), linear_cols=linear_cols, **gkw)
        self.noise_dim = self.draft.noise_dim

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        d = self.draft(cond, m, eps=eps).reshape(B * m, -1)
        tm = float(self.flow.flow["tau_min"])
        x = (1 - tm) * torch.randn_like(d) + tm * d
        return self.flow.integrate(cond.repeat_interleave(m, 0), x, tm).view(B, m, -1)


# ---------------------------------------------------------------- MF2: RML


class RMLGenerator(Tables):
    """Reverse Markov Learning with K steps. Forward chain x_k = sqrt(a_k) x_{k-1} + sqrt(1 - a_k) e, abar_k = cos^2(pi k / 2K)
    (abar_K = 0: x_K is pure noise). One shared Engression net g(cond, x_k, onehot(k - 1), noise) draws x_{k-1}; trained with the
    shipped score for the last step (k = 1, the profile) and almost-fair CRPS + energy score in standardised space for the noised steps."""
    own_loss = True

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, rml=None, **gkw):
        super().__init__()
        self.K = int((rml or {}).get("K", 3))
        self.n_out, self.noise_dim = n_out, noise_dim
        ab = np.cos(np.pi / 2 * np.arange(self.K + 1) / self.K) ** 2
        ab[-1] = 0.0
        self.register_buffer("abar", torch.tensor(ab, dtype=torch.float32), persistent=False)
        self.net = Generator(n_cond + n_out + self.K, n_out, noise_dim, width, depth, **gkw)

    def step_input(self, c, x, k):                        # k: (N,) long, 1..K (the step from x_k to x_{k-1})
        return torch.cat([c, x, nn.functional.one_hot(k - 1, self.K).to(c.dtype)], -1)

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        c = cond.repeat_interleave(m, 0)
        x = torch.randn(len(c), self.n_out, device=cond.device)
        for k in range(self.K, 0, -1):
            x = self.net(self.step_input(c, x, torch.full((len(c),), k, device=c.device, dtype=torch.long)), 1)[:, 0].to(x.dtype)
        return x.view(B, m, -1)

    def train_loss(self, c, t, ctx):
        B, cfg = len(c), ctx["cfg"]
        k = torch.randint(1, self.K + 1, (B,), device=c.device)
        ab_prev, ab_k = self.abar[k - 1][:, None], self.abar[k][:, None]
        x_prev = ab_prev.sqrt() * t + (1 - ab_prev).sqrt() * torch.randn_like(t)
        a = ab_k / ab_prev
        x_k = a.sqrt() * x_prev + (1 - a).sqrt() * torch.randn_like(t)
        with _ac(c):
            s = self.net(self.step_input(c, x_k, k), cfg["m"]).float()
        last = k == 1
        ps = ctx["phys_std"]
        loss = 0.0
        if last.any():
            top = ctx["top"][last] if ctx["top"] is not None else None
            loss = loss + last.float().mean() * ctx["score"](s[last], t[last], top)
        if (~last).any():
            sn, yn = ps(s[~last]), ps(x_prev[~last])
            loss = loss + (~last).float().mean() * (afcrps(sn, yn, cfg["crps_alpha"]) + cfg["es_weight"] * energy_score(sn, yn) / math.sqrt(yn.shape[-1]))
        return loss


# ---------------------------------------------------------------- GT1: height-autoregressive


def har_blocks(n_blocks, n_out):
    """-> list of column-index arrays: block b = its heights for all 4 variables; block 0 also holds the surface columns."""
    out = []
    for b, hs in enumerate(np.array_split(np.arange(N_H), n_blocks)):
        cols = np.concatenate([v * N_H + hs for v in range(N_V)])
        if b == 0:
            cols = np.concatenate([cols, np.arange(N_PROF, n_out)])
        out.append(np.sort(cols))
    return out


class HARGenerator(Tables):
    """Bottom-to-top generation in `blocks` height blocks. One shared Engression net sees (cond, everything generated so far with zeros
    above, onehot(block)) and its own noise; only the current block's columns are kept. Trained end to end on the shipped score
    (the train loop's ordinary path), so gradients flow through the whole chain."""

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, har=None, **gkw):
        super().__init__()
        self.nb = int((har or {}).get("blocks", 7))
        self.n_out, self.noise_dim = n_out, noise_dim
        for b, cols in enumerate(har_blocks(self.nb, n_out)):
            self.register_buffer(f"cols{b}", torch.tensor(cols, dtype=torch.long), persistent=False)
        self.net = Generator(n_cond + n_out + self.nb, n_out, noise_dim, width, depth, **gkw)

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        c = cond.repeat_interleave(m, 0)
        x = torch.zeros(len(c), self.n_out, device=cond.device, dtype=cond.dtype)
        for b in range(self.nb):
            oh = torch.zeros(len(c), self.nb, device=c.device, dtype=c.dtype)
            oh[:, b] = 1
            o = self.net(torch.cat([c, x, oh], -1), 1)[:, 0].to(x.dtype)
            cols = getattr(self, f"cols{b}")
            x = x.index_copy(1, cols, o[:, cols])
        return x.view(B, m, -1)


# ---------------------------------------------------------------- H3: mixture of experts


class ExpertHead(nn.Module):
    """Replaces Generator.head[1]: base linear (the draft) + E expert deltas; a gate on the draft's 0-3 km lapse rate, its ~5.5 km wind
    speed and the season (doy sin / cos) gives soft weights; each sample picks one expert by those weights (straight-through)."""

    def __init__(self, width, n_out, E, balance, i3, i55):
        super().__init__()
        self.base = nn.Linear(width, n_out)
        self.experts = nn.ModuleList(nn.Linear(width, n_out) for _ in range(E))
        for e in self.experts:
            nn.init.normal_(e.weight, std=0.1 / math.sqrt(width))
            nn.init.zeros_(e.bias)
        self.gate = nn.Sequential(nn.Linear(4, 32), nn.SiLU(), nn.Linear(32, E))
        self.space = Space(n_out)
        self.E, self.balance, self.i3, self.i55 = E, balance, i3, i55
        self.ctx = None
        self.aux_loss = self.last_gate = None

    def features(self, draft):
        p = self.space.to_std(draft) * self.space.ps + self.space.pm                 # physical profiles of the draft
        iT, iu, iv = PROFILE.index("T") * N_H, PROFILE.index("u") * N_H, PROFILE.index("v") * N_H
        lapse = (p[..., iT] - p[..., iT + self.i3]) / (HEIGHTS[self.i3] / 1000.0)   # K/km over 0-3 km
        w55 = torch.hypot(p[..., iu + self.i55], p[..., iv + self.i55])
        return torch.stack([(lapse - 6.5) / 3.0, (w55 - 20.0) / 10.0], -1)

    def forward(self, hn):
        draft = self.base(hn)
        f = torch.cat([self.features(draft.detach().float()), self.ctx.to(hn.dtype).unsqueeze(1).expand(*hn.shape[:2], 2)], -1)
        probs = torch.softmax(self.gate(f.to(hn.dtype)).float(), -1)                # (B, m, E)
        pick = torch.multinomial(probs.reshape(-1, self.E), 1).view(*probs.shape[:2])
        hard = nn.functional.one_hot(pick, self.E).float()
        w = hard + probs - probs.detach()                                           # straight-through: forward one expert, gradient to the gate
        out = draft + sum(w[..., e:e + 1].to(hn.dtype) * self.experts[e](hn) for e in range(self.E))
        self.last_gate = probs.detach()
        self.aux_loss = self.balance * self.E * (hard.mean((0, 1)) * probs.mean((0, 1))).sum() if self.training else None
        return out


class MoEGenerator(Generator, Tables):
    """H3: the shipped Generator with its output layer replaced by ExpertHead. moe = dict(E=3, balance=0.01, doy_cols=[i, j])."""

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, moe=None, **gkw):
        super().__init__(n_cond, n_out, noise_dim, width, depth, **gkw)
        o = {**dict(E=3, balance=0.01), **(moe or {})}
        hs = np.asarray(HEIGHTS, float)
        self.doy_cols = list(o["doy_cols"])
        self.head[1] = ExpertHead(width, n_out, int(o["E"]), float(o["balance"]), int(np.argmin(abs(hs - 3000))), int(np.argmin(abs(hs - 5500))))
        self.n_out = n_out

    @property
    def aux_loss(self):
        return self.head[1].aux_loss

    def forward(self, cond, m=1, eps=None):
        self.head[1].ctx = cond[:, self.doy_cols]
        if not self.training:
            self.head[1].aux_loss = None
        return super().forward(cond, m, eps)


# ---------------------------------------------------------------- H4: EOF large scale + AR(1) small scale


class EOFGenerator(Tables):
    """The net outputs k EOF coefficients (standardised-profile space), the 3 surface values (normalised) and 2 numbers per
    (variable, band): amplitude and correlation length of an AR(1)-in-height small-scale draw. Loss: the shipped score on the
    large scale against the EOF-filtered target, plus almost-fair CRPS of the small scale against the remainder."""
    own_loss = True

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, eof=None, **gkw):
        super().__init__()
        self.k = int((eof or {})["k"])
        self.n_out, self.noise_dim, self.n_sfc = n_out, noise_dim, n_out - N_PROF
        self.register_buffer("basis", torch.zeros(self.k, N_PROF))                  # rows: orthonormal EOFs of standardised profiles
        self.register_buffer("band", torch.tensor(band_of_heights(), dtype=torch.long), persistent=False)
        self.register_buffer("dz", torch.tensor(np.diff(np.asarray(HEIGHTS, float)) / 1000.0, dtype=torch.float32), persistent=False)
        self.space = Space(n_out)
        self.nb = len(BAND_EDGES) + 1
        self.net = Generator(n_cond, self.k + self.n_sfc + 2 * N_V * self.nb, noise_dim, width, depth, **gkw)

    def parts(self, cond, m):
        o = self.net(cond, m).float()
        k, ns = self.k, self.n_sfc
        large = o[..., :k] @ self.basis                                             # (B, m, N_PROF) standardised
        sfc = o[..., k:k + ns]
        ar = o[..., k + ns:].reshape(*o.shape[:2], N_V, 2, self.nb)
        amp = nn.functional.softplus(ar[..., 0, :])[..., self.band]                 # (B, m, N_V, N_H)
        L = nn.functional.softplus(ar[..., 1, :])[..., self.band[1:]] + 0.05       # km, per layer
        rho = torch.exp(-self.dz / L)
        z = torch.randn_like(amp)
        e = [amp[..., 0] * z[..., 0]]
        for h in range(1, N_H):
            r = rho[..., h - 1]
            e.append(r * e[-1] * amp[..., h] / amp[..., h - 1].clamp_min(1e-4) + amp[..., h] * (1 - r * r).clamp_min(1e-6).sqrt() * z[..., h])
        small = torch.stack(e, -1).flatten(-2)
        return large, small, sfc

    def assemble(self, large, sfc):                       # standardised profile + normalised surface -> normalised differences
        sfc_std = (sfc * self.space.ts[N_PROF:] + self.space.tm[N_PROF:] - self.space.pm[N_PROF:]) / self.space.ps[N_PROF:]
        return self.space.from_std(torch.cat([large, sfc_std], -1))

    def forward(self, cond, m=1, eps=None):
        large, small, sfc = self.parts(cond, m)
        return self.assemble(large + small, sfc)

    def train_loss(self, c, t, ctx):
        with _ac(c):
            large, small, sfc = self.parts(c, ctx["cfg"]["m"])
        y = self.space.to_std(t)[..., :N_PROF]
        y_large = (y @ self.basis.T) @ self.basis
        t_large = self.assemble(y_large, t[..., N_PROF:])
        loss = ctx["score"](self.assemble(large, sfc), t_large, ctx["top"])
        return loss + afcrps(small, y - y_large, ctx["cfg"]["crps_alpha"])


# ---------------------------------------------------------------- H1: statistical prior + residual


class PriorResidual(Tables):
    """prior = dict(mode="gram" | "noise", doy=[col sin, col cos], mu=[2], sd=[2]). "gram": a sample of the monthly mean / sd per column
    with AR(1) height correlation per variable (fitted on training rows, standardised-profile space) is fed to the net as an extra input,
    and the output is that sample (as normalised differences) + the net's correction. "noise" (the control): the extra input is fresh
    N(0, 1) of the same size and nothing is added.
    shortcut: the prior is box-wide per month (not per site as the station gramlike stand-in); upgrade to per grid cell if H1 is close."""

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, prior=None, **gkw):
        super().__init__()
        self.o = dict(prior or {})
        self.n_out, self.noise_dim = n_out, noise_dim
        self.register_buffer("mean", torch.zeros(12, n_out))
        self.register_buffer("sd", torch.ones(12, n_out))
        self.register_buffer("rho", torch.zeros(N_V, N_H - 1))
        self.space = Space(n_out)
        self.net = Generator(n_cond + n_out, n_out, noise_dim, width, depth, **gkw)

    def month(self, cond):
        dc, mu, sd = self.o["doy"], self.o["mu"], self.o["sd"]
        s, c = cond[:, dc[0]] * sd[0] + mu[0], cond[:, dc[1]] * sd[1] + mu[1]
        doy = torch.remainder(torch.atan2(s, c), 2 * math.pi) / (2 * math.pi) * 365.25
        return torch.clamp((doy / 365.25 * 12).long(), 0, 11)

    def draw(self, cond):                                 # (N,) rows -> (N, n_out) standardised prior sample
        mo = self.month(cond)
        z = torch.randn(len(cond), self.n_out, device=cond.device)
        zp = z[:, :N_PROF].reshape(-1, N_V, N_H)
        e = [zp[..., 0]]
        for h in range(1, N_H):
            r = self.rho[:, h - 1]
            e.append(r * e[-1] + (1 - r * r).clamp_min(1e-6).sqrt() * zp[..., h])
        z = torch.cat([torch.stack(e, -1).flatten(1), z[:, N_PROF:]], 1)
        return self.mean[mo] + self.sd[mo] * z

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        c = cond.repeat_interleave(m, 0)
        if self.o.get("mode", "gram") == "noise":
            return self.net(torch.cat([c, torch.randn(len(c), self.n_out, device=c.device)], -1), 1)[:, 0].view(B, m, -1)
        p = self.draw(c)
        out = self.space.from_std(p) + self.net(torch.cat([c, p.to(c.dtype)], -1), 1)[:, 0].float()
        return out.view(B, m, -1)


# ---------------------------------------------------------------- H2: analog + warp


class AnalogGenerator(Tables):
    """analog = dict(R, feat=[cond cols], year_col, year_mu, year_sd, k=8, corr=0.1). Buffers: feats (R, F) normalised inputs, targ (R, n_out)
    normalised differences, years (R,) of thinned training rows. Each row's k nearest analogs (Euclidean on the normalised `feat` columns,
    own year excluded); each member gets one at random. The net sees (cond, analog) and outputs per (variable, band) a shift and a
    log-scale (interpolated linearly between band centres) plus a free correction scaled by `corr`, applied in standardised-profile space.
    shortcut: torch brute-force kNN in chunks (sklearn cannot take GPU tensors); fine for <= ~300k table rows."""

    def __init__(self, n_cond, n_out, noise_dim=32, width=512, depth=4, analog=None, **gkw):
        super().__init__()
        self.o = {**dict(k=8, corr=0.1), **(analog or {})}
        R, F = int(self.o["R"]), len(self.o["feat"])
        self.n_out, self.noise_dim = n_out, noise_dim
        self.register_buffer("feats", torch.zeros(R, F))
        self.register_buffer("targ", torch.zeros(R, n_out))
        self.register_buffer("years", torch.zeros(R, dtype=torch.int32))
        self.space = Space(n_out)
        nb = len(BAND_EDGES) + 1
        hs = np.asarray(HEIGHTS, float)
        cen = np.array([np.mean(hs[band_of_heights() == b]) for b in range(nb)])
        W = np.stack([np.interp(hs, cen, np.eye(nb)[b]) for b in range(nb)], 1)    # (N_H, nb) linear interpolation weights
        self.register_buffer("W", torch.tensor(W, dtype=torch.float32), persistent=False)
        self.nb = nb
        self.net = Generator(n_cond + n_out, 2 * N_V * nb + n_out, noise_dim, width, depth, **gkw)

    @torch.no_grad()
    def neighbours(self, cond):
        f = cond[:, self.o["feat"]].float()
        yr = torch.round(cond[:, self.o["year_col"]].float() * self.o["year_sd"] + self.o["year_mu"]).int()
        k = int(self.o["k"])
        best_d = torch.full((len(f), k), float("inf"), device=f.device)
        best_i = torch.zeros((len(f), k), dtype=torch.long, device=f.device)
        for a in range(0, len(self.feats), 65536):
            d = torch.cdist(f, self.feats[a:a + 65536])
            d = d.masked_fill(self.years[a:a + 65536][None] == yr[:, None], float("inf"))
            dd, ii = torch.topk(torch.cat([best_d, d], 1), k, largest=False)
            best_i = torch.gather(torch.cat([best_i, torch.arange(a, a + d.shape[1], device=f.device).expand(len(f), -1)], 1), 1, ii)
            best_d = dd
        return best_i

    def forward(self, cond, m=1, eps=None):
        B = len(cond)
        nbr = torch.cat([self.neighbours(cond[i:i + 1024]) for i in range(0, B, 1024)])          # (B, k)
        pick = nbr.gather(1, torch.randint(0, nbr.shape[1], (B, m), device=cond.device)).reshape(-1)
        a = self.targ[pick]                                                                      # (B*m, n_out) normalised differences
        c = cond.repeat_interleave(m, 0)
        o = self.net(torch.cat([c, a.to(c.dtype)], -1), 1)[:, 0].float()
        nb = self.nb
        sh = o[:, :N_V * nb].view(-1, N_V, nb) @ self.W.T                                         # (N, N_V, N_H)
        ls = (o[:, N_V * nb:2 * N_V * nb].view(-1, N_V, nb) @ self.W.T).clamp(-3, 3)
        corr = o[:, 2 * N_V * nb:]
        A = self.space.to_std(a)
        prof = A[:, :N_PROF].view(-1, N_V, N_H) * torch.exp(ls) + sh
        P = torch.cat([prof.flatten(1), A[:, N_PROF:]], 1) + float(self.o["corr"]) * corr
        return self.space.from_std(P).view(B, m, -1)


# ---------------------------------------------------------------- build / prepare / teacher

_CLASSES = dict(flow=FlowGenerator, rml=RMLGenerator, har=HARGenerator, moe=MoEGenerator, eof=EOFGenerator, prior=PriorResidual,
                analog=AnalogGenerator, refine=RefineGenerator)


def build(arch, n_cond, n_out, noise_dim=32, width=512, depth=4, **kw):
    if arch not in _CLASSES:
        raise ValueError(f"unknown generator arch {arch!r}; known: mlp, tokens, {', '.join(_CLASSES)}")
    return _CLASSES[arch](n_cond, n_out, noise_dim, width, depth, **kw)


def _space_tables(d, prefix="space."):
    tref = np.asarray(d["tref"], np.float64)
    p = tref[:, :N_PROF].reshape(len(tref), N_V, N_H).cumsum(-1).reshape(len(tref), N_PROF)
    ph = np.concatenate([p, tref[:, N_PROF:]], 1)
    safe = lambda s: np.where(s > 1e-6, s, 1.0)
    return {prefix + "tm": d["tm"], prefix + "ts": d["ts"], prefix + "pm": ph.mean(0), prefix + "ps": safe(ph.std(0))}, ph


def prepare(cfg, d, log=print):
    """-> (model_kw additions, tables for model.set_tables). d: train.py's training-only arrays (cond, ref, tref, tr_idx, targets, cm, cs,
    tm, ts, names, n_prof, year). Nothing here sees validation or test rows."""
    arch, o = cfg["arch"], dict(cfg.get("s25") or {})
    if arch not in _CLASSES:
        raise ValueError(f"unknown generator arch {arch!r}")
    if arch != "flow" and not d["n_prof"]:
        raise ValueError(f"arch {arch} needs the 179-column profile targets")
    names, cm, cs = d["names"], d["cm"], d["cs"]
    if arch == "flow":
        return {"flow": {k: o[k] for k in ("steps", "train", "train_steps", "tau_min") if k in o}}, None
    if arch == "rml":
        return {"rml": dict(K=int(o.get("K", 3)))}, None
    if arch == "har":
        return {"har": dict(blocks=int(o.get("blocks", 7)))}, None
    if arch == "refine":
        raise ValueError("arch refine is composed from two trained checkpoints by scripts/s25_compose_refine.py, not trained")
    tabs, ph = _space_tables(d, "space." if arch != "moe" else "head.1.space.")
    if arch == "moe":
        dc = [names.index("doy_sin"), names.index("doy_cos")]
        return {"moe": dict(E=int(o.get("E", 3)), balance=float(o.get("balance", 0.01)), doy_cols=dc)}, tabs
    P = (ph - tabs["space.pm"]) / tabs["space.ps"]                                           # standardised training profiles
    if arch == "eof":
        _, sv, vt = np.linalg.svd(P[:, :N_PROF] - P[:, :N_PROF].mean(0), full_matrices=False)
        frac = np.cumsum(sv ** 2) / np.sum(sv ** 2)
        k = int(np.searchsorted(frac, float(o.get("eof_var", 0.95))) + 1)
        log(f"eof: k = {k} EOFs hold {frac[k - 1]:.3f} of the standardised-profile variance")
        return {"eof": dict(k=k)}, {**tabs, "basis": vt[:k]}
    if arch == "prior":
        dc = [names.index("doy_sin"), names.index("doy_cos")]
        kw = {"prior": dict(mode=str(o.get("mode", "gram")), doy=dc, mu=[float(cm[i]) for i in dc], sd=[float(cs[i]) for i in dc])}
        cond_ref = np.asarray(d["cond"][d["ref"]], np.float64)
        doy = np.mod(np.arctan2(cond_ref[:, dc[0]], cond_ref[:, dc[1]]), 2 * np.pi) / (2 * np.pi) * 365.25
        mo = np.clip((doy / 365.25 * 12).astype(int), 0, 11)
        mean = np.stack([P[mo == k].mean(0) for k in range(12)])
        sd = np.stack([np.maximum(P[mo == k].std(0), 1e-3) for k in range(12)])
        a = ((P - mean[mo]) / sd[mo])[:, :N_PROF].reshape(len(P), N_V, N_H)
        rho = np.clip((a[..., 1:] * a[..., :-1]).mean(0) / np.sqrt((a[..., 1:] ** 2).mean(0) * (a[..., :-1] ** 2).mean(0)), 0.0, 0.999)
        return kw, {**tabs, "mean": mean, "sd": sd, "rho": rho}
    if arch == "analog":                                  # thinned table of training rows (1991-2020 with the 25.1 split)
        lin = set(cfg["linear_features"]) | set(cfg.get("ignore_inputs") or [])
        feat = [i for i, n in enumerate(names) if n not in lin]
        yc = names.index("year")
        F = len(feat)
        max_rows = int(o.get("max_mb", 200) * 1e6 // ((F + len(d["tm"]) + 1) * 4))
        R = min(int(o.get("rows", max_rows)), max_rows, len(d["tr_idx"]))
        rows = np.sort(np.random.default_rng(4242).choice(d["tr_idx"], R, replace=False))
        cond = np.asarray(d["cond"][rows], np.float64)
        feats = ((cond - cm) / cs)[:, feat]
        targ = (d["targets"](rows) - d["tm"]) / d["ts"]
        log(f"analog: table of {R:,} training rows ({R / len(d['tr_idx']):.1%} of them), {R * (F + len(d['tm']) + 1) * 4 / 1e6:.0f} MB, features {[names[i] for i in feat]}")
        kw = {"analog": dict(R=R, feat=feat, year_col=yc, year_mu=float(cm[yc]), year_sd=float(cs[yc]), k=int(o.get("k", 8)), corr=float(o.get("corr", 0.1)))}
        return kw, {**tabs, "feats": feats, "targ": targ, "years": np.round(cond[:, yc]).astype(np.int32)}
    raise AssertionError(arch)


class _Teacher(nn.Module):
    def __init__(self, models):
        super().__init__()
        self.models = nn.ModuleList(models)

    @torch.no_grad()
    def forward(self, c, k):
        n = -(-k // len(self.models))
        return torch.cat([mdl(c, n) for mdl in self.models], 1)[:, :k]


def load_teacher(path, norm, device):
    """MF1: a trained checkpoint (any arch, one file or an ensemble) -> frozen sampler f(c, k) -> (B, k, n_out) in the same normalised space.
    Refuses a teacher whose normalisation differs from the student's (they must be trained on the same data and split)."""
    from tempest.generator.model import make_generator
    ck = torch.load(path, map_location="cpu", weights_only=True)
    models = []
    for mb in ck.get("members", [ck]):
        for key in ("cm", "cs", "tm", "ts"):
            if not torch.allclose(torch.as_tensor(mb["norm"][key]).float(), norm[key].float(), rtol=1e-5, atol=1e-6):
                raise ValueError(f"teacher {path} has a different normalisation ({key}); train the student on the same data, years and seed")
        c = mb["cfg"]
        mdl = make_generator(c.get("arch", "mlp"), mb["n_cond"], mb["n_out"], c["noise_dim"], c["width"], c["depth"], linear_cols=mb.get("linear_cols"),
                             **({"product_pairs": mb["product_pairs"]} if mb.get("product_pairs") else {}), **mb.get("model_kw", {}))
        mdl.load_state_dict(mb["state"])
        models.append(mdl.to(device).eval().requires_grad_(False))
    return _Teacher(models).to(device)
