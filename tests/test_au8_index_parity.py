"""AU-8 (New_Plan 15.3): the tool's index forecast (tempest_weather/sources/indices.py) equals tempest.ingest.index_forecast on the shipped snapshot."""
import pathlib
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from tempest.ingest import index_forecast as fc
from tempest_weather.sources.indices import COLS, Indices

SNAP = pathlib.Path(__file__).parents[1] / "tempest_weather" / "assets" / "indices.npz"


@pytest.mark.parametrize("h", [1, 6, 12])
def test_tool_forecast_equals_the_ingest_ridge(h):
    z = np.load(SNAP)
    ind = Indices(z)
    y, m = divmod(ind.last(), 100)
    k = y * 12 + m - 1 + h
    mean, cov, hh = ind.forecast(datetime(k // 12, k % 12 + 1, 15))
    assert hh == h
    months = pd.to_datetime([f"{v // 100}-{v % 100:02d}-01" for v in ind.months])
    tab = pd.DataFrame({c: np.asarray(z[c], float) for c in COLS}, index=months)
    f = fc.fit(tab, months[-1], h)
    x = (fc._design(tab.dropna(subset=COLS), np.array([f["pos"]]), f["qbo_sd"]) - f["mean_x"]) / f["sd_x"]
    mean_i = f["mean_y"] + f["scale"] * (x @ f["beta"])[0]
    cov_i = f["cov"] * np.outer(f["scale"], f["scale"])
    assert np.allclose(mean, mean_i, rtol=1e-6, atol=0)
    assert np.allclose(cov, cov_i, rtol=5e-3, atol=0)     # ddof 1 (tool) vs 0 (ingest) in the residual sd: n / (n - 1) with n ~ 500
