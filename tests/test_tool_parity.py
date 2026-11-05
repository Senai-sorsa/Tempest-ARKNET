"""The standalone tool folder reproduces the main package: same weights + same noise -> same samples; copied numerics agree."""
import os

import numpy as np
import pytest
import torch

from tempest.calibrate import spread
from tempest.generator import sample as S
from tempest.generator.model import Generator
from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS
from tempest_weather import _core, engine

ASSET = "tempest_weather/assets/model.npz"
CKPT = "models/generator_80_p2f.pt"
needs_assets = pytest.mark.skipif(not (os.path.exists(ASSET) and os.path.exists(CKPT)), reason="exported assets / checkpoint not present")


@needs_assets
def test_numpy_generator_matches_torch_for_the_same_noise():
    net = engine.Net.load(ASSET)
    ck = torch.load(CKPT, map_location="cpu", weights_only=True)
    rng = np.random.default_rng(0)
    cond = np.stack([rng.uniform(31, 34, 64), rng.uniform(-108, -101, 64), rng.uniform(800, 1800, 64), rng.uniform(800, 1800, 64), rng.uniform(-1, 1, 64), rng.uniform(-1, 1, 64),
                     rng.uniform(-1, 1, 64), rng.uniform(-1, 1, 64), rng.uniform(2000, 2030, 64), rng.normal(0, 1, 64), rng.normal(0, 1e13, 64), rng.normal(0, 10, 64), rng.normal(0, 8, 64)], 1).astype(np.float32)
    eps = rng.standard_normal((64, net.meta["noise_dim"])).astype(np.float32)
    ours = net.sample(cond, eps=eps)
    K = len(ck["members"])
    ref = np.empty_like(ours)
    for i, m in enumerate(ck["members"]):
        c = m["cfg"]
        model = Generator(m["n_cond"], m["n_out"], c["noise_dim"], c["width"], c["depth"], linear_cols=m["linear_cols"])
        model.load_state_dict(m["state"])
        model.eval()
        n = m["norm"]
        torch.manual_seed(5)
        e_t = torch.randn(len(cond[i::K]), 1, c["noise_dim"])
        e_use = torch.from_numpy(eps[i::K])
        # run the torch model with exactly our noise by replacing its random draw
        with torch.no_grad():
            orig = torch.randn
            torch.randn = lambda *a, **k: e_use.reshape(*a)
            try:
                y = model((torch.from_numpy(cond[i::K]) - n["cm"]) / n["cs"], 1)[:, 0] * n["ts"] + n["tm"]
            finally:
                torch.randn = orig
        ref[i::K] = y.numpy()
    so = ck["members"][0]["sp_offset"]
    ref[:, so[0]] += S.standard_pressure(cond[:, so[1]]).astype(np.float32)
    assert np.allclose(ours, ref, rtol=2e-4, atol=2e-3), np.abs(ours - ref).max()


def test_copied_numerics_match_the_originals():
    rng = np.random.default_rng(1)
    raw = rng.normal(size=(7, 179)).astype(np.float32)
    raw[:, 2 * 44] += 280
    for tgt in ("rh", "dpd"):
        S.set_rh_target(tgt)
        assert np.allclose(_core.to_physical(raw.copy(), tgt), S.to_physical(raw.copy()), atol=1e-4, equal_nan=True)
    S.set_rh_target("rh")
    assert np.array_equal(_core.HEIGHTS, HEIGHTS)
    z = HEIGHTS.astype(float)
    T = np.tile(np.linspace(300, 215, 44), (3, 1)) + rng.normal(0, 1, (3, 44))
    rh = rng.uniform(5, 95, (3, 44))
    a, b = thermo.column(z, T, rh, np.full(3, 87000.0), z_sfc=1400.0), _core.thermo_column(z, T, rh, np.full(3, 87000.0), z_sfc=1400.0)
    assert all(np.allclose(a[k], b[k]) for k in a)
    cal = dict(qz=np.sort(rng.normal(size=(110, 179)), 0), qu=np.sort(rng.normal(size=(110, 179)) * 1.1, 0), m=np.array(199))
    x = rng.normal(size=(3, 199, 179)).astype(np.float32)
    x[..., 2 * 44] += 280
    assert np.allclose(spread.apply(cal, x), _core.calibrate(cal, x), atol=1e-4)
