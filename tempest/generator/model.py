"""Engression generator (Shen & Meinshausen, arXiv 2307.00835): noise enters at the input, trained on the energy score."""
import torch
from torch import nn


class Generator(nn.Module):
    def __init__(self, n_cond: int, n_out: int, noise_dim: int = 32, width: int = 512, depth: int = 5):
        super().__init__()
        layers, d = [], n_cond + noise_dim
        for _ in range(depth - 1):
            layers += [nn.Linear(d, width), nn.SiLU()]
            d = width
        layers.append(nn.Linear(d, n_out))
        self.net = nn.Sequential(*layers)
        self.noise_dim = noise_dim

    def forward(self, cond: torch.Tensor, m: int = 1) -> torch.Tensor:
        """cond (B, F) normalised -> m samples per row, (B, m, n_out) normalised."""
        c = cond.unsqueeze(1).expand(-1, m, -1)
        eps = torch.randn(*c.shape[:2], self.noise_dim, device=cond.device, dtype=cond.dtype)
        return self.net(torch.cat([c, eps], dim=-1))


def energy_score(samples: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Unbiased energy score, mean over the batch. samples (B, m, D) with m >= 2, y (B, D). Lower is better."""
    m = samples.shape[1]
    fit = (samples - y.unsqueeze(1)).norm(dim=-1).mean(dim=1)
    spread = sum((samples[:, i] - samples[:, j]).norm(dim=-1) for i in range(m) for j in range(i + 1, m))
    return (fit - spread / (m * (m - 1) / 2) / 2).mean()
