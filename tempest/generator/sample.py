"""Draw profiles from a trained generator checkpoint."""
import numpy as np
import torch

from tempest.generator.model import Generator


class Sampler:
    def __init__(self, ckpt, device=None):
        if not isinstance(ckpt, dict):
            ckpt = torch.load(ckpt, map_location="cpu", weights_only=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        c = ckpt["cfg"]
        self.model = Generator(ckpt["n_cond"], ckpt["n_out"], c["noise_dim"], c["width"], c["depth"])
        self.model.load_state_dict(ckpt["state"])
        self.model.to(self.device).eval()
        self.norm = {k: v.to(self.device) for k, v in ckpt["norm"].items()}

    @torch.no_grad()
    def __call__(self, cond: np.ndarray) -> np.ndarray:
        """cond (N, F) raw features, one row per sample (drivers already drawn) -> (N, D) raw targets."""
        n = self.norm
        c = (torch.as_tensor(cond, dtype=torch.float32, device=self.device) - n["cm"]) / n["cs"]
        return (self.model(c, 1)[:, 0] * n["ts"] + n["tm"]).cpu().numpy()
