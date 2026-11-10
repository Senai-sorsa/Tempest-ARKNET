"""IL-182 (2026-11-10): the region fitters must work on a box that is not NM/TX: a 9 x 9 grid (not 29 longitudes), another latitude (other distance bins) and missing upper heights at
high-terrain points (the Denver store). The first Denver run gave an all-NaN lag table and an EMPTY distance table; this runs both fitters on a small synthetic store like that."""
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

xr = pytest.importorskip("xarray")
pytest.importorskip("zarr")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _store(path):
    from tempest.profiles.to_heights import HEIGHTS
    lat = np.repeat(np.arange(40.0, 37.99, -0.25), 9)
    lon = np.tile(np.arange(-106.0, -103.99, 0.25), 9)
    t = pd.DatetimeIndex([x for y in (2005, 2023) for mo in (1, 4, 7, 10) for x in pd.date_range(f"{y}-{mo:02d}-01", periods=24 * 3, freq="h")])   # every season, fit and check windows
    rng = np.random.default_rng(0)
    nh, npt, nt = len(HEIGHTS), len(lat), len(t)
    base = np.cumsum(rng.normal(size=(npt, nt, 1)), 1) * 0.3 + rng.normal(size=(npt, nt, nh)) * 0.2   # temporally coherent anomalies
    data = {}
    for k, off in (("u", 5.0), ("v", 0.0), ("T", 280.0), ("RH", 50.0)):
        x = (off + base + rng.normal(size=(npt, nt, nh)) * 0.1).astype(np.float32)
        x[:6, rng.random(nt) < 0.05, -3:] = np.nan                                                     # high-terrain points: top heights missing in 5 % of hours
        data[k] = (("point", "time", "height"), x)
    for k in ("t2m", "sp", "rh2m"):
        data[k] = (("point", "time"), np.ones((npt, nt), np.float32))
    ds = xr.Dataset(data, coords=dict(time=t.values, height=np.asarray(HEIGHTS), lat=("point", lat), lon=("point", lon), z_sfc=("point", np.full(npt, 1600.0))))
    ds.to_zarr(path, mode="w")


@pytest.mark.parametrize("script,args", [("c1_fit_lagcorr.py", ["--points", "spread"]), ("c2_fit_distcorr.py", ["--auto-grid"])])
def test_fitters_on_a_9x9_box_with_missing_heights(tmp_path, script, args):
    store, out = str(tmp_path / "p.zarr"), str(tmp_path / "out.npz")
    _store(store)
    env = dict(os.environ, PYTHONPATH=REPO)
    r = subprocess.run([sys.executable, "-W", "ignore", os.path.join(REPO, "scripts", script), "--stores", store, "--out", out] + args, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    z = np.load(out)
    rho = z["rho"]
    assert rho.size and np.isfinite(rho).mean() > 0.9, f"table mostly NaN: {np.isfinite(rho).mean():.2f}"
    assert np.nanmax(np.abs(rho)) <= 1.0 + 1e-6
    if "km" in z.files:
        assert len(z["km"]) >= 4 and z["km"][0] == 0.0                                                 # the box's own separations, not dropped
        assert abs(z["km"][1] - 0.25 * 111.0 * np.cos(np.radians(39.0))) < 2.0                          # first bin = one longitude step at 39 N (about 21.6 km), not NM/TX's 24
