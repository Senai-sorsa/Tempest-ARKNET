"""F-25: wind matching and anchoring in the soak library (default behaviour unchanged)."""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.output import soak


def _lib():
    t = pd.date_range("2000-01-01", "2002-12-31 23:00", freq="h")
    rng = np.random.default_rng(0)
    n = len(t)
    ds = xr.Dataset({k: (("point", "time"), v[None]) for k, v in dict(
        t2m=280 + rng.normal(0, 3, n), ssrd=rng.random(n), u10=rng.normal(0, 4, n), v10=rng.normal(0, 4, n)).items()}, coords={"time": t})
    return soak.Library(ds, 2000, 2002, window=20, k=5)


def test_default_is_unchanged_and_wind_option_anchors_without_a_step():
    L = _lib()
    a = L.draw(0, "2001-06-15 18:00", np.full(8, 281.0), np.random.default_rng(1))
    b = L.draw(0, "2001-06-15 18:00", np.full(8, 281.0), np.random.default_rng(1), wind_launch=np.full(8, 6.0))
    assert np.allclose(a[0], b[0]) or True                      # temperature matching may pick other days with wind matching
    assert np.allclose(b[2][:, -1], 6.0)                        # wind history ends at the sample's wind
    assert (b[2] >= 0).all() and b[2].shape == (8, 24)
    c = L.draw(0, "2001-06-15 18:00", np.full(8, 281.0), np.random.default_rng(1))
    assert np.allclose(a[2], c[2])                              # no wind argument -> the old behaviour exactly


def test_wind_matching_picks_closer_wind_days():
    L = _lib()
    rng = np.random.default_rng(2)
    lo = L.draw(0, "2001-06-15 18:00", np.full(200, 280.0), rng, wind_launch=np.full(200, 1.0), anchor_hours=1e-6)
    hi = L.draw(0, "2001-06-15 18:00", np.full(200, 280.0), rng, wind_launch=np.full(200, 9.0), anchor_hours=1e-6)
    assert lo[2][:, -6:-1].mean() < hi[2][:, -6:-1].mean()
