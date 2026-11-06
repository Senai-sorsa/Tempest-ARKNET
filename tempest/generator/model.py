"""Engression generator (Shen & Meinshausen, arXiv 2307.00835): noise enters the network, trained on proper scores.

Layout follows the ML weather ensembles (ECMWF AIFS-CRPS arXiv 2412.15832, DeepMind FGN arXiv 2506.10772):
residual blocks whose layer norms are shifted and scaled by an embedding of one low-dimensional noise vector, so
every layer sees the same random draw; trained on the per-value almost-fair CRPS.
"""
import math

import torch
import torch.utils.checkpoint
from torch import nn


class Block(nn.Module):
    """Pre-norm residual MLP block; the norm's scale/shift come from the noise embedding (conditional layer norm)."""

    def __init__(self, width: int, emb: int, ctx_film: bool = False):
        super().__init__()
        self.norm = nn.LayerNorm(width, elementwise_affine=False)
        self.film = nn.Linear(emb, 2 * width)
        nn.init.zeros_(self.film.weight)  # starts as a plain layer norm
        nn.init.zeros_(self.film.bias)
        if ctx_film:   # place context gets its own scale/shift instead of sharing the noise FiLM's weights
            self.cfilm = nn.Linear(emb, 2 * width)
            nn.init.zeros_(self.cfilm.weight)
            nn.init.zeros_(self.cfilm.bias)
        self.ff = nn.Sequential(nn.Linear(width, width), nn.SiLU(), nn.Linear(width, width))

    def forward(self, h, z, zc=None):
        s, b = self.film(z).chunk(2, dim=-1)
        if zc is not None:
            sc, bc = self.cfilm(zc).chunk(2, dim=-1)
            s, b = s + sc, b + bc
        return h + self.ff(self.norm(h) * (1 + s) + b)


class Generator(nn.Module):
    """depth: number of residual blocks. linear_cols: indices of inputs kept out of the main network (year and
    the ENSO/QBO indices). Each enters as output += slope_k(other inputs) * input_k, a straight-line effect whose
    size is learned per place, season, hour and height. Year: dates past the training years extrapolate along
    the learned trend. Indices: inside the main network their four monthly values fingerprint each month and it
    memorises that month's weather (held-out error rose within one pass); a straight-line effect cannot."""

    def __init__(self, n_cond: int, n_out: int, noise_dim: int = 32, width: int = 512, depth: int = 4,
                 linear_cols: list[int] | None = None, interactions: bool = False, product_pairs: list | None = None,
                 geo: dict | None = None, context_cols: list[int] | None = None, terrain_head: dict | None = None,
                 ctx_sep: bool = False, noise_t: dict | None = None, jump: dict | None = None):
        """Loop-3 options, all off by default (= the adopted network, same parameters and outputs):
        geo = dict(cols=[lat, lon positions], mu=[..], sd=[..], L=10, siren=0): spherical harmonics of the real
          lat/lon (un-normalised with mu/sd) replace the two raw columns; siren > 0 passes them through a 2-layer
          sine network of that width first.
        context_cols: positions of place inputs (terrain, climatology; plus the geo encoding when geo is set) that
          go through a context network whose output joins the noise embedding in every block's FiLM, instead of
          being concatenated at the input.
        terrain_head = dict(cols=[...], height=[n_out metres]): output += exp(-height / H) * MLP(terrain), H learned.
        geo["w0"] (default 1): SIREN first-layer frequency; > 1 uses the SIREN-paper init (U(+-1/fan_in) times w0).
        ctx_sep: with context_cols, the context embedding feeds its own zero-initialised FiLM in every block (and is not
          added to the noise embedding), so place shifts and noise spread are modulated separately (Gemini review).
        noise_t = dict(dims=8, nu=4): the first `dims` noise numbers are Student-t (unit variance) instead of Gaussian, so heavy
          tails (shear sheets) need not be built from Gaussian noise by the network (Gemini idea 1, the cheap part).
        jump = dict(K=2, top=3000, height=[n_h], n_var=4, inv_ts=[n_var*n_h]): K sharp steps per sample, each with its centre
          (0..top m), width and per-variable size, added to the profile as tanh steps (= bumps in the step targets); sizes start
          at 0 (Gemini idea 3: inversions and shear sheets as explicit jumps)."""
        super().__init__()
        self.linear_cols = list(linear_cols or [])
        self.geo = dict(geo) if geo else None
        self.context_cols = list(context_cols or [])
        drop = set(self.linear_cols) | set(self.geo["cols"] if self.geo else []) | set(self.context_cols)
        self.keep_cols = [i for i in range(n_cond) if i not in drop]
        self.noise_dim = noise_dim
        self.product_pairs = [tuple(p) for p in (product_pairs or [])]     # IL-97: pairs of POSITIONS in linear_cols whose product is one more straight-line effect (ONI x QBO ...)
        self.interactions = interactions       # F-14: the slope network also sees the driver columns themselves, so a driver's effect can depend on the other drivers (ONI x QBO, ONI x WWV)
        n_geo = 0
        if self.geo:
            self.register_buffer("geo_mu", torch.tensor(self.geo["mu"], dtype=torch.float32))
            self.register_buffer("geo_sd", torch.tensor(self.geo["sd"], dtype=torch.float32))
            n_geo = (self.geo["L"] + 1) ** 2
            if self.geo.get("siren"):
                w = self.geo["siren"]
                self.siren = nn.ModuleList([nn.Linear(n_geo, w), nn.Linear(w, w)])
                for lin in self.siren:
                    nn.init.uniform_(lin.weight, -math.sqrt(6 / lin.in_features), math.sqrt(6 / lin.in_features))
                self.siren_w0 = float(self.geo.get("w0", 1.0))
                if self.siren_w0 != 1.0:
                    nn.init.uniform_(self.siren[0].weight, -1 / n_geo, 1 / n_geo)
                n_geo = w
        n_in = len(self.keep_cols) + (0 if self.context_cols else n_geo)
        emb = 128
        self.embed = nn.Sequential(nn.Linear(noise_dim, emb), nn.SiLU(), nn.Linear(emb, emb), nn.LayerNorm(emb))
        if self.context_cols:
            self.ctx = nn.Sequential(nn.Linear(len(self.context_cols) + n_geo, emb), nn.SiLU(), nn.Linear(emb, emb), nn.LayerNorm(emb))
        self.inp = nn.Linear(n_in + noise_dim, width)
        self.ctx_sep = bool(ctx_sep and self.context_cols)
        self.blocks = nn.ModuleList(Block(width, emb, self.ctx_sep) for _ in range(depth))
        self.head = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, n_out))
        self.noise_t = dict(noise_t) if noise_t else None
        self.jump = dict(jump) if jump else None
        if self.jump:
            K, nv = int(self.jump["K"]), int(self.jump["n_var"])
            self.jump_net = nn.Linear(width, K * (nv + 2))
            nn.init.zeros_(self.jump_net.weight)     # sizes 0 at start (centres top/2, widths ~90 m until sizes grow)
            nn.init.zeros_(self.jump_net.bias)
            self.register_buffer("jump_z", torch.tensor(self.jump["height"], dtype=torch.float32))
            self.register_buffer("jump_inv_ts", torch.tensor(self.jump["inv_ts"], dtype=torch.float32))
        self.th = dict(terrain_head) if terrain_head else None
        if self.th:
            self.th_net = nn.Sequential(nn.Linear(len(self.th["cols"]), 64), nn.SiLU(), nn.Linear(64, n_out))
            nn.init.zeros_(self.th_net[-1].weight)   # starts with no effect
            nn.init.zeros_(self.th_net[-1].bias)
            self.register_buffer("th_height", torch.tensor(self.th["height"], dtype=torch.float32))
            self.th_logH = nn.Parameter(torch.tensor(math.log(1000.0)))
        n_slope = len(self.keep_cols) + len(self.context_cols) + n_geo   # the slope network still sees the whole place
        if self.linear_cols:
            self.slope = nn.Sequential(nn.Linear(n_cond if interactions else n_slope, 128), nn.SiLU(), nn.Linear(128, n_out * (len(self.linear_cols) + len(self.product_pairs))))
            nn.init.zeros_(self.slope[-1].weight)  # start with no effect; training adds what the data supports
            nn.init.zeros_(self.slope[-1].bias)

    def forward(self, cond: torch.Tensor, m: int = 1) -> torch.Tensor:
        """cond (B, F) normalised -> m samples per row, (B, m, n_out) normalised."""
        full = slope_in = cond
        g = self._geo(full) if self.geo else None
        place = ([full[:, self.context_cols]] if self.context_cols else []) + ([g] if g is not None else [])
        if self.linear_cols:
            x = full[:, self.linear_cols]
        cond = full[:, self.keep_cols]
        if g is not None and not self.context_cols:
            cond = torch.cat([cond, g], -1)
        if self.linear_cols and not self.interactions:
            slope_in = torch.cat([full[:, self.keep_cols]] + place, -1) if place else cond
        c = cond.unsqueeze(1).expand(-1, m, -1)
        eps = torch.randn(*c.shape[:2], self.noise_dim, device=cond.device, dtype=cond.dtype)
        if self.noise_t:
            d, nu = int(self.noise_t["dims"]), float(self.noise_t["nu"])
            chi = torch.distributions.Chi2(torch.tensor(nu, device=cond.device)).sample((*c.shape[:2], d)).to(eps.dtype)
            eps = torch.cat([eps[..., :d] / torch.sqrt(chi / nu) * math.sqrt((nu - 2) / nu), eps[..., d:]], -1)
        z = self.embed(eps)
        zc = None
        if self.context_cols:
            zc = self.ctx(torch.cat(place, -1)).unsqueeze(1)
            if not self.ctx_sep:
                z, zc = z + zc, None
        h = self.inp(torch.cat([c, eps], dim=-1))
        for blk in self.blocks:
            h = blk(h, z, zc)
        out = self.head(h)
        if self.jump:
            out = out + self._jumps(h, out.shape[-1])
        if self.th:
            out = out + (torch.exp(-self.th_height / torch.exp(self.th_logH)) * self.th_net(full[:, self.th["cols"]])).unsqueeze(1)
        if self.linear_cols:
            if self.product_pairs:
                x = torch.cat([x, torch.stack([x[:, a] * x[:, b] for a, b in self.product_pairs], 1)], 1)
            s = self.slope(slope_in).view(len(cond), x.shape[1], -1)
            out = out + torch.einsum("bk,bkd->bd", x, s).unsqueeze(1)
        return out

    def _jumps(self, h, n_out):
        K, nv, nh = int(self.jump["K"]), int(self.jump["n_var"]), len(self.jump_z)
        p = self.jump_net(h).view(*h.shape[:-1], K, nv + 2)
        a, c = p[..., :nv], float(self.jump["top"]) * torch.sigmoid(p[..., nv])         # size per variable, centre (m)
        w = 20.0 + 100.0 * nn.functional.softplus(p[..., nv + 1])                        # width (m), >= 20
        t = torch.tanh((self.jump_z - c.unsqueeze(-1)) / w.unsqueeze(-1))                 # (..., K, nh)
        step = torch.cat([torch.zeros_like(t[..., :1]), t[..., 1:] - t[..., :-1]], -1)    # profile step -> target step columns
        add = torch.einsum("...kv,...kh->...vh", a, step).reshape(*h.shape[:-1], nv * nh) * self.jump_inv_ts
        return torch.cat([add, add.new_zeros(*add.shape[:-1], n_out - nv * nh)], -1)

    def _geo(self, full):
        from tempest.geo.sh import sh
        raw = full[:, self.geo["cols"]].float() * self.geo_sd + self.geo_mu      # back to degrees
        y = sh(raw[:, 0], raw[:, 1], self.geo["L"]).to(full.dtype)
        if self.geo.get("siren"):
            y = torch.sin(self.siren[1](torch.sin(self.siren_w0 * self.siren[0](y))))
        return y


class TokBlock(nn.Module):
    """Pre-norm transformer block over the height tokens; layer-norm scale/shift come from the noise embedding, as in Block."""

    def __init__(self, d: int, heads: int, emb: int):
        super().__init__()
        self.n1 = nn.LayerNorm(d, elementwise_affine=False)
        self.n2 = nn.LayerNorm(d, elementwise_affine=False)
        self.film = nn.Linear(emb, 4 * d)
        nn.init.zeros_(self.film.weight)
        nn.init.zeros_(self.film.bias)
        self.attn = nn.MultiheadAttention(d, heads, batch_first=True)
        self.ff = nn.Sequential(nn.Linear(d, 2 * d), nn.SiLU(), nn.Linear(2 * d, d))

    def forward(self, h, z):
        if self.training and torch.is_grad_enabled():   # recompute in the backward pass: 44 tokens per sample would not fit otherwise
            return torch.utils.checkpoint.checkpoint(self._f, h, z, use_reentrant=False)
        return self._f(h, z)

    def _f(self, h, z):
        s1, b1, s2, b2 = (t.unsqueeze(1) for t in self.film(z).chunk(4, dim=-1))
        x = self.n1(h) * (1 + s1) + b1
        h = h + self.attn(x, x, x, need_weights=False)[0]
        return h + self.ff(self.n2(h) * (1 + s2) + b2)


class TokenGenerator(nn.Module):
    """Same inputs, noise and outputs as Generator, but the profile is built by attention along height (improvement-loop IL-8, idea from Chronos-2's
    patch tokens): one token per height, carrying the context vector plus a learned height embedding; transformer blocks let every height look at every
    other; each token emits its n_var values (u, v, T, RH). The columns after the n_var x n_height profile columns (surface fields, anything extra) come from
    a linear head on the mean token. Output order is variable-major like the dataset's targets."""

    def __init__(self, n_cond: int, n_out: int, noise_dim: int = 32, width: int = 512, depth: int = 4,
                 linear_cols: list[int] | None = None, n_height: int = 44, n_var: int = 4, d: int = 128, heads: int = 4):
        super().__init__()
        self.linear_cols = list(linear_cols or [])
        self.keep_cols = [i for i in range(n_cond) if i not in self.linear_cols]
        self.noise_dim, self.n_out, self.nh, self.nv = noise_dim, n_out, n_height, n_var
        assert n_out >= n_height * n_var
        n_in = len(self.keep_cols)
        emb = 128
        self.embed = nn.Sequential(nn.Linear(noise_dim, emb), nn.SiLU(), nn.Linear(emb, emb), nn.LayerNorm(emb))
        self.inp = nn.Sequential(nn.Linear(n_in + noise_dim, width), nn.SiLU(), nn.Linear(width, d))
        self.height = nn.Parameter(torch.randn(n_height, d) * 0.02)
        self.blocks = nn.ModuleList(TokBlock(d, heads, emb) for _ in range(depth))
        self.norm = nn.LayerNorm(d)
        self.tok_out = nn.Linear(d, n_var)
        self.extra = nn.Linear(d, n_out - n_height * n_var) if n_out > n_height * n_var else None
        if self.linear_cols:
            self.slope = nn.Sequential(nn.Linear(n_in, 128), nn.SiLU(), nn.Linear(128, n_out * len(self.linear_cols)))
            nn.init.zeros_(self.slope[-1].weight)
            nn.init.zeros_(self.slope[-1].bias)

    def forward(self, cond: torch.Tensor, m: int = 1) -> torch.Tensor:
        if self.linear_cols:
            x = cond[:, self.linear_cols]
            cond = cond[:, self.keep_cols]
        B = cond.shape[0]
        c = cond.unsqueeze(1).expand(-1, m, -1)
        eps = torch.randn(B, m, self.noise_dim, device=cond.device, dtype=cond.dtype)
        z = self.embed(eps).reshape(B * m, -1)
        h = self.inp(torch.cat([c, eps], dim=-1)).reshape(B * m, 1, -1) + self.height.unsqueeze(0)   # (B m, H, d)
        for blk in self.blocks:
            h = blk(h, z)
        h = self.norm(h)
        prof = self.tok_out(h).transpose(1, 2).reshape(B, m, self.nv * self.nh)                       # variable-major
        out = prof if self.extra is None else torch.cat([prof, self.extra(h.mean(1)).reshape(B, m, -1)], -1)
        if self.linear_cols:
            s = self.slope(cond).view(len(cond), len(self.linear_cols), -1)
            out = out + torch.einsum("bk,bkd->bd", x, s).unsqueeze(1)
        return out


def make_generator(arch, *args, **kw):
    """arch "mlp" (default, the adopted model) or "tokens" (IL-8)."""
    return (TokenGenerator if arch == "tokens" else Generator)(*args, **kw)


def energy_score(samples: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Unbiased energy score, mean over the batch. samples (B, m, D) with m >= 2, y (B, D). Lower is better."""
    m = samples.shape[1]
    fit = (samples - y.unsqueeze(1)).norm(dim=-1).mean(dim=1)
    spread = sum((samples[:, i] - samples[:, j]).norm(dim=-1) for i in range(m) for j in range(i + 1, m))
    return (fit - spread / (m * (m - 1) / 2) / 2).mean()


def afcrps(samples: torch.Tensor, y: torch.Tensor, alpha: float = 0.95) -> torch.Tensor:
    """Almost-fair CRPS (AIFS-CRPS, arXiv 2412.15832), mean over batch and values. samples (B, m, D), m >= 2.
    alpha = 1 is the fair CRPS (unbiased for any m but has a degenerate optimum); 0.95 avoids it."""
    m = samples.shape[1]
    eps = (1 - alpha) / m
    fit = (samples - y.unsqueeze(1)).abs().mean(dim=1)
    spread = (samples.unsqueeze(1) - samples.unsqueeze(2)).abs().sum(dim=(1, 2))
    return (fit - (1 - eps) * spread / (2 * m * (m - 1))).mean()
