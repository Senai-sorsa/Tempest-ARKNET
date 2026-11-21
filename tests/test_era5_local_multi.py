"""A24 (2026-11-10): TEMPEST_ERA5_STORE may list a day store and a night store; past mode then has every UTC hour. Small synthetic zarr stores, no real data."""
import os

import numpy as np
import pytest

xr = pytest.importorskip("xarray")
pytest.importorskip("zarr")

from tempest_weather.sources import era5_local as E


def _store(path, hours, base):
    t = np.array([np.datetime64("2024-07-04T00") + np.timedelta64(int(h), "h") for h in hours])
    npt, nh = 2, 44
    data = {k: (("point", "time", "height"), np.full((npt, len(t), nh), base, np.float32)) for k in ("u", "v", "T", "RH")}
    data.update({k: (("point", "time"), np.full((npt, len(t)), base, np.float32)) for k in ("t2m", "sp", "rh2m")})
    data["z_sfc"] = (("point",), np.array([1000.0, 1200.0], np.float32))
    ds = xr.Dataset(data, coords=dict(time=t, lat=("point", [32.0, 33.0]), lon=("point", [-107.0, -106.0])))
    ds.to_zarr(path, mode="w")
    return path


def test_day_and_night_stores_join_to_all_hours(tmp_path, monkeypatch):
    day = _store(str(tmp_path / "day.zarr"), [0, 1, 2, 3, 4, 12, 13, 23], 1.0)
    night = _store(str(tmp_path / "night.zarr"), [4, 5, 6, 11], 2.0)          # 04 UTC in both: the first store wins
    both = day + os.pathsep + night
    monkeypatch.setenv(E.ENV, both)
    assert E.default_path() == both
    s = E.open_store(both)
    t = s.time.values
    assert (np.diff(t.astype("int64")) > 0).all() and len(t) == 11
    assert E.profile(s, 32.0, -107.0, "2024-07-04T06:00")["t2m"] == 2.0       # night hour from the night store
    assert E.profile(s, 32.0, -107.0, "2024-07-04T04:00")["t2m"] == 1.0       # duplicated hour from the first store
    assert E.profile(s, 33.0, -106.0, "2024-07-04T13:00")["elev"] == 1200.0
    with pytest.raises(LookupError, match="night store"):
        E.profile(s, 32.0, -107.0, "2024-07-04T08:00")
    monkeypatch.setenv(E.ENV, day + os.pathsep + str(tmp_path / "missing.zarr"))
    assert E.default_path() is None                                            # every listed store must exist
    assert len(E.open_store(day).time) == 8                                    # one path: as before
