"""New_Plan 28.11: the tool's numpy X4-R offset (tempest_weather.engine.Net, exported by tempest.export_tool.pack) equals the torch
X4-R model's shift over the base on the same noise, and is 0 outside the fitted area. Skips when the checkpoints are not on disk."""
import os

import numpy as np
import pytest
import torch

X4R, BASE = "models/s25/c4wx4r_s0.pt", "models/l3_c4w.pt"
DATA = ("data/train/denver_full_fill_dpd.npz", "data/train/pilot80_l21_all24_dpd.npz")
pytestmark = pytest.mark.skipif(not all(map(os.path.exists, (X4R, BASE) + DATA)), reason="X4-R checkpoints or their datasets not on disk")


def _net(ck, tmp_path, tag):
    from tempest.export_tool import pack
    from tempest_weather.engine import Net
    arr = {}
    pack(ck, "", arr)
    f = tmp_path / f"{tag}.npz"
    np.savez(f, **arr)
    return Net.load(str(f))


def test_x4r_port_matches_torch(tmp_path):
    from tempest.generator.sample import Sampler
    from tempest.generator.train import _load
    cond = np.concatenate([np.asarray(_load(p)["cond"][:300], np.float32) for p in DATA])
    ck, base = (torch.load(p, map_location="cpu", weights_only=True) for p in (X4R, BASE))
    net = _net(ck, tmp_path, "x4r")
    off = net.x4r_offset(cond)
    torch.manual_seed(1); t1 = Sampler(ck)(cond)
    torch.manual_seed(1); t0 = Sampler(base)(cond)
    ts = ck["members"][0]["norm"]["ts"].numpy()
    assert float((np.abs((t1 - t0) - off) / ts).max()) < 1e-3
    far = cond[:5].copy()
    far[:, net.names.index("lat")] = 60.0
    assert not np.abs(net.x4r_offset(far)).any()
    assert getattr(_net(base, tmp_path, "base"), "x4r", None) is None      # a plain checkpoint exports exactly as before
