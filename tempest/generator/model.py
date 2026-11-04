"""Engression generator (Shen & Meinshausen, arXiv 2307.00835): noise enters the network, trained on proper scores.

Layout follows the ML weather ensembles (ECMWF AIFS-CRPS arXiv 2412.15832, DeepMind FGN arXiv 2506.10772):
residual blocks whose layer norms are shifted and scaled by an embedding of one low-dimensional noise vector, so
every layer sees the same random draw; trained on the per-value almost-fair CRPS.
"""
import torch
from torch import nn


class Block(nn.Module):
    """Pre-norm residual MLP block; the norm's scale/shift come from the noise embedding (conditional layer norm)."""

    def __init__(self, width: int, emb: int):
        super().__init__()
        self.norm = nn.LayerNorm(width, elementwise_affine=False)
        self.film = nn.Linear(emb, 2 * width)
        nn.init.zeros_(self.film.weight)  # starts as a plain layer norm
        nn.init.zeros_(self.film.bias)
        self.ff = nn.Sequential(nn.Linear(width, width), nn.SiLU(), nn.Linear(width, width))

    def forward(self, h, z):
        s, b = self.film(z).chunk(2, dim=-1)
        return h + self.ff(self.norm(h) * (1 + s) + b)


class Generator(nn.Module):
    """depth: number of residual blocks. linear_cols: indices of inputs kept out of the main network (year and
    the ENSO/QBO indices). Each enters as output += slope_k(other inputs) * input_k, a straight-line effect whose
    size is learned per place, season, hour and height. Year: dates past the training years extrapolate along
    the learned trend. Indices: inside the main network their four monthly values fingerprint each month and it
    memorises that month's weather (held-out error rose within one pass); a straight-line effect cannot."""

    def __init__(self, n_cond: int, n_out: int, noise_dim: int = 32, width: int = 512, depth: int = 4,
                 linear_cols: list[int] | None = None):
        super().__init__()
        self.linear_cols = list(linear_cols or [])
        self.keep_cols = [i for i in range(n_cond) if i not in self.linear_cols]
        self.noise_dim = noise_dim
        n_in = len(self.keep_cols)
        emb = 128
        self.embed = nn.Sequential(nn.Linear(noise_dim, emb), nn.SiLU(), nn.Linear(emb, emb), nn.LayerNorm(emb))
        self.inp = nn.Linear(n_in + noise_dim, width)
        self.blocks = nn.ModuleList(Block(width, emb) for _ in range(depth))
        self.head = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, n_out))
        if self.linear_cols:
            self.slope = nn.Sequential(nn.Linear(n_in, 128), nn.SiLU(), nn.Linear(128, n_out * len(self.linear_cols)))
            nn.init.zeros_(self.slope[-1].weight)  # start with no effect; training adds what the data supports
            nn.init.zeros_(self.slope[-1].bias)

    def forward(self, cond: torch.Tensor, m: int = 1) -> torch.Tensor:
        """cond (B, F) normalised -> m samples per row, (B, m, n_out) normalised."""
        if self.linear_cols:
            x = cond[:, self.linear_cols]
            cond = cond[:, self.keep_cols]
        c = cond.unsqueeze(1).expand(-1, m, -1)
        eps = torch.randn(*c.shape[:2], self.noise_dim, device=cond.device, dtype=cond.dtype)
        z = self.embed(eps)
        h = self.inp(torch.cat([c, eps], dim=-1))
        for blk in self.blocks:
            h = blk(h, z)
        out = self.head(h)
        if self.linear_cols:
            s = self.slope(cond).view(len(cond), len(self.linear_cols), -1)
            out = out + torch.einsum("bk,bkd->bd", x, s).unsqueeze(1)
        return out


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
