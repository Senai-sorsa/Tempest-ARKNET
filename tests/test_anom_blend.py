def test_anom_blend_mask():
    import torch
    from tempest.generator.model import Generator, N_ANOM_BASIS
    torch.manual_seed(0)
    nc, no = 8, 3
    def g(mask):
        a = dict(cols=[0,1,2,3,4,5], mu=[0.]*6, sd=[1.]*6, P=2, tm=[0.]*no, ts=[1.]*no, mean_only=True)
        if mask is not None: a["mask"] = mask
        m = Generator(nc, no, noise_dim=4, width=16, depth=1, anom=a)
        m.set_anom(torch.tensor([[0.,0.],[10.,10.]]), torch.randn(2, N_ANOM_BASIS, no), torch.zeros(2, N_ANOM_BASIS, no))
        return m
    full = torch.randn(5, nc); z = torch.randn(5, 4, no)
    m1 = g(None); off = m1._anom(full, z) - z
    mh = g([0.5, 0.5, 0.0]); mh.load_state_dict({k: v for k, v in m1.state_dict().items()}, strict=False)
    mh.anom_keys.copy_(m1.anom_keys); mh.anom_cmu.copy_(m1.anom_cmu)
    oh = mh._anom(full, z) - z
    assert torch.allclose(oh[..., :2], 0.5 * off[..., :2], atol=1e-6) and torch.allclose(oh[..., 2], torch.zeros_like(oh[..., 2])), "blend mask wrong"
