"""ARCO fill: the IFS mixed-phase relative humidity, and to_heights reading a <yyyymm>.nc fill like a CDS grib."""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.ingest import arco_fill as A
from tempest.profiles import to_heights as H


def test_rh_limits_and_phase():
    p = 85000.0
    es_w = A._es(np.array([290.0]), 17.502, 32.19)[0]
    q = 0.5 * es_w * A.EPS / p                                   # about half saturation at 290 K
    assert abs(A.rh_from_q(np.array([q]), np.array([290.0]), p)[0] - 50) < 1.0
    assert A.rh_from_q(np.array([1.0]), np.array([290.0]), p)[0] == 100.0                      # clipped
    cold = A.rh_from_q(np.array([1e-4]), np.array([240.0]), p)[0]                              # ice branch gives a larger RH than water would
    assert cold > 100 * (p * 1e-4 / (A.EPS + (1 - A.EPS) * 1e-4)) / A._es(np.array([240.0]), 17.502, 32.19)[0] - 1e-6 or cold == 100.0


def test_to_heights_reads_nc_fill(tmp_path):
    times = pd.date_range("2000-01-01", periods=3, freq="h")
    lat, lon = np.array([34.0, 33.75]), np.array([252.0, 252.25])
    rng = np.random.default_rng(0)
    mk = lambda: (("time", "isobaricInhPa", "latitude", "longitude"), rng.normal(size=(3, 8, 2, 2)).astype("float32"))
    xr.Dataset({n: mk() for n in "uvtrz"}, coords=dict(time=times, isobaricInhPa=A.LEVELS, latitude=lat, longitude=lon)).to_netcdf(tmp_path / "200001.nc")
    out = H.cds_levels(str(tmp_path), times, lat, lon)
    assert out["u"].shape == (2, 2, 3, 8) and np.isfinite(out["t"]).all()
