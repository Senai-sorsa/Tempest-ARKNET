"""G6: dryden.synthesize(spectrum='karman') keeps the turbulence envelopes (sigma(z)) and gives a correlation that falls with separation; the default ('dryden') is unchanged."""
import numpy as np
import pytest

from tempest_weather.flight import dryden


def _inputs(n=400):
    z = np.array([10.0, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000])
    u = np.tile(np.linspace(4, 14, len(z)), (n, 1))
    v = np.zeros_like(u)
    T = np.tile(np.linspace(300, 285, len(z)), (n, 1))
    return z, u, v, T


def test_karman_keeps_sigma_and_decorrelates():
    z, u, v, T = _inputs()
    out = dryden.synthesize(z, u, v, T, dz=5.0, seed=1, spectrum="karman")
    zf = out["z"]
    for comp, sig in (("w_turb", "sigma_w"), ("u_turb", "sigma_u")):
        x = out[comp]
        ratios = [x[:, int(np.argmin(np.abs(zf - h)))].std() / out[sig][:, int(np.argmin(np.abs(zf - h)))].mean() for h in (20, 100, 300, 500, 1500)]
        assert abs(np.mean(ratios) - 1.0) < 0.06                               # envelope kept on average (a per-row sample normalisation overstated it by about 10 %)
        i = int(np.argmin(np.abs(zf - 300.0)))
        c_near = np.corrcoef(x[:, i], x[:, i + 1])[0, 1]
        c_far = np.corrcoef(x[:, i], x[:, min(i + 200, x.shape[1] - 1)])[0, 1]
        assert c_near > 0.8 and c_far < c_near
    with pytest.raises(ValueError):
        dryden.synthesize(z, u, v, T, spectrum="nonsense")


def test_default_is_unchanged():
    z, u, v, T = _inputs(20)
    a = dryden.synthesize(z, u, v, T, dz=5.0, seed=3)
    b = dryden.synthesize(z, u, v, T, dz=5.0, seed=3, spectrum="dryden", uw_corr=None)
    assert all(np.array_equal(a[k], b[k]) for k in ("u_turb", "v_turb", "w_turb"))
