"""Review item F-4: two samplers with different humidity targets / feature lists used alternately must not corrupt each other."""
import numpy as np
import torch

from tempest.generator import features, sample
from tempest.generator.model import Generator


def _ckpt(rh_target, names):
    torch.manual_seed(0)
    g = Generator(len(names), 179, 4, 16, 1)
    norm = dict(cm=torch.zeros(len(names)), cs=torch.ones(len(names)), tm=torch.zeros(179), ts=torch.ones(179))
    return dict(state=g.state_dict(), cfg=dict(noise_dim=4, width=16, depth=1), norm=norm, n_cond=len(names), n_out=179, linear_cols=[], sp_offset=None,
                rh_target=rh_target, cond_names=names)


def test_samplers_reapply_their_own_settings():
    a = sample.Sampler(_ckpt("rh", list(features.BASE_FEATURES)), device="cpu")
    b = sample.Sampler(_ckpt("dpd", list(features.P2_FEATURES)), device="cpu")
    assert sample.RH_TARGET == "dpd" and features.FEATURES == features.P2_FEATURES      # the last one created is active
    a(np.zeros((2, len(features.BASE_FEATURES)), np.float32))
    assert sample.RH_TARGET == "rh" and features.FEATURES == features.BASE_FEATURES      # a sampling call restores a's own settings
    b(np.zeros((2, len(features.P2_FEATURES)), np.float32))
    assert sample.RH_TARGET == "dpd" and features.FEATURES == features.P2_FEATURES
    features.set_active(list(features.BASE_FEATURES))
    sample.set_rh_target("rh")
