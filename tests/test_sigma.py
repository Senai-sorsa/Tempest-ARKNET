"""SIGMA stage 2 tables (tempest/forecast/sigma.py): recovers a known beta and s, and the target / draw round trip is exact."""
import numpy as np

from tempest.forecast import sigma as SG


def _rows(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    lead = rng.choice([0.5, 1.0, 3.0, 5.0, 9.5], n)
    month = rng.integers(0, 12, n)
    valid = (np.datetime64("2016-01-15T00") + (month * 31 * 24).astype("timedelta64[h]")).astype("datetime64[ns]")
    lat, lon = rng.choice([32.0, 33.0], n), np.full(n, -105.0)
    clim = 10.0 + 5.0 * (lat == 33.0)
    anom_f = rng.normal(0, 2, (n, 2))
    b_true = np.where(lead[:, None] <= 1, 0.9, np.where(lead[:, None] <= 5, 0.6, 0.2))
    obs = clim[:, None] + b_true * anom_f + rng.normal(0, 1, (n, 2))
    return dict(year=np.full(n, 2016), valid=valid, lat=lat, lon=lon, valid_utc_hour=np.full(n, 12), lead_days=lead,
                obs=obs, hres=clim[:, None] + anom_f), b_true


def test_tables_recover_beta():
    d, _ = _rows()
    tab = SG.fit(d)
    assert abs(tab["beta"][0, 0] - 0.9) < 0.05 and abs(tab["beta"][2, 0] - 0.6) < 0.05 and abs(tab["beta"][9, 0] - 0.2) < 0.05
    assert np.allclose(tab["beta"][1], tab["beta"][0]) or np.allclose(tab["beta"][1], tab["beta"][2])     # day 2 had no rows: nearest day
    assert tab["srel"].min() >= SG.S_FLOOR


def test_round_trip_and_fallback():
    d, _ = _rows()
    tab = SG.fit(d)
    t = SG.target(tab, d)
    back = SG.to_residual(tab, d, t[:, None, :])[:, 0] + d["hres"]
    assert np.allclose(back, d["obs"], atol=1e-3)
    new = {k: v[:5].copy() for k, v in d.items()}
    new["lat"] = np.full(5, 40.0)                                           # unseen place -> month x hour fallback, no error
    base, s = SG.base_scale(tab, new)
    assert np.isfinite(base).all() and (s > 0).all()


def test_fit_years_guard():
    d, _ = _rows(200)
    d["year"] = np.full(200, 2022)
    try:
        SG.fit(d)
    except AssertionError:
        return
    raise AssertionError("2022 rows must be refused")
