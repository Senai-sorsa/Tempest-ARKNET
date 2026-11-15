"""New_Plan 17 (UR1-UR15) code: the new modules and the opt-in flags. No data files needed except where a test says so (then it skips)."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(REPO, "new_plan_kit"), os.path.join(REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tempest.calibrate import tropo   # noqa: E402
from tempest.forecast import sigma as SG   # noqa: E402
from tempest.forecast import tailcal as TC   # noqa: E402
from tempest.forecast.modeF import HEIGHTS, PROFILE   # noqa: E402
from tempest.scoring.score import coverage90   # noqa: E402


def _members(n=1500, m=199, C=4, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.standard_t(3, size=(n, C)).astype(np.float32)
    x = rng.normal(0, 1.7, size=(n, m, C)).astype(np.float32)
    return x, y, np.array(["u", "u", "T", "RH"]), np.repeat([1, 3, 5], n // 3)


def test_tailcal_fixes_99_and_keeps_the_middle():
    x, y, vc, lead = _members()
    x[:, :, 3] = np.clip(50 + 20 * x[:, :, 3], 0, 100)
    y[:, 3] = np.clip(50 + 20 * y[:, 3], 0, 100)
    tab = TC.fit(x, y, lead, vc)
    x2 = TC.apply(tab, x, lead, vc)
    assert abs(coverage90(x2[:, :, :3], y[:, :3], 0.99).mean() - 0.99) < 0.006
    assert np.array_equal(coverage90(x, y, 0.90), coverage90(x2, y, 0.90))                 # the scorer's 90 % range is untouched
    assert np.array_equal(np.argsort(x2[:20], 1, kind="stable"), np.argsort(x[:20], 1, kind="stable"))
    assert x2[:, :, 3].min() >= 0 and x2[:, :, 3].max() <= 100                            # RH held inside 0-100 %


def test_tailcal_unknown_lead_or_variable_is_unchanged_and_round_trips(tmp_path):
    x, y, vc, lead = _members(n=900)
    tab = TC.fit(x, y, lead, vc)
    other = TC.apply(tab, x[:5], np.full(5, 99), vc)
    assert np.array_equal(other, x[:5])
    TC.save(tmp_path / "t.npz", tab)
    back = TC.load(tmp_path / "t.npz")
    assert np.array_equal(TC.apply(back, x[:50], lead[:50], vc), TC.apply(tab, x[:50], lead[:50], vc))


def _sigma_rows(n=6000, seed=1, ens=False):
    rng = np.random.default_rng(seed)
    C = len(PROFILE) * len(HEIGHTS)
    obs = rng.normal(0, 1, (n, len(PROFILE), len(HEIGHTS))).astype(np.float32)
    d = dict(obs=obs, hres=(obs + rng.normal(0, 0.5, obs.shape)).astype(np.float32), valid=np.datetime64("2018-01-01T00") + np.arange(n).astype("timedelta64[h]"),
             lat=rng.choice([32.0, 33.0], n), lon=rng.choice([-106.0, -105.0], n), valid_utc_hour=rng.choice([0, 12], n), lead_days=rng.uniform(0.25, 10, n), year=np.full(n, 2018))
    if ens:
        d["ens"] = np.abs(rng.normal(1, 0.3, (n, 24))).astype(np.float32)
    assert d["obs"].reshape(n, -1).shape[1] == C
    return d


def test_sigma_ens_scale_is_opt_in():
    d = _sigma_rows(ens=True)
    plain, scaled = SG.fit(d), SG.fit(d, ens_scale=True)
    assert "ens_med" not in plain and "ens_med" in scaled
    assert np.array_equal(plain["beta"], SG.fit({k: v for k, v in d.items() if k != "ens"})["beta"])   # an `ens` field alone changes nothing
    b0, s0 = SG.base_scale(plain, d)
    b1, s1 = SG.base_scale(scaled, d)
    assert np.allclose(b0, b1)
    f = s1 / (scaled["srel"][SG.lead_day(d["lead_days"]) - 1] * scaled["csd"][np.asarray(d["valid"]).astype("datetime64[M]").astype(np.int64) % 12])
    assert f.min() >= 0.8 - 1e-6 and f.max() <= 1.5 + 1e-6
    col = SG.ens_columns()
    assert np.allclose(f[:, col < 0], 1.0) and (col[np.repeat(np.asarray(PROFILE), len(HEIGHTS)) == "RH"] < 0).all()


def test_tropopause_and_quantile_map():
    z = np.arange(0.0, 20001.0, 250.0)
    T = np.stack([np.where(z < h, 288 - 6.5 * z / 1000, 288 - 6.5 * h / 1000 + 0.5 * (z - h) / 1000) for h in (10000.0, 14000.0)])
    assert np.allclose(tropo.tropopause(T, z), [10000.0, 14000.0], atol=250)
    assert np.isnan(tropo.tropopause(np.full((1, len(z)), np.nan), z)[0])
    rng = np.random.default_rng(0)
    x, y = rng.normal(0, 1, (300, 30, 5)), rng.normal(2, 1, (300, 5))
    r = np.tile(np.linspace(-1500, 1500, 5), (300, 1))
    qm = tropo.fit_qmap(x, y, r, r)
    x2 = tropo.apply_qmap(qm, x, r)
    assert abs(x2.mean() - 2) < 0.15
    assert np.array_equal(tropo.apply_qmap(qm, x, r + 1e6), x)                             # outside every bin: unchanged


def test_ur2_mix_rows_units():
    if not os.path.exists(os.path.join(REPO, "models", "modeF_bl.npz")):
        pytest.skip("models/modeF_bl.npz not on disk")
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        import ur2_mix_rows as U                                                            # runs its own unit checks on import
    finally:
        os.chdir(cwd)
    assert U.family_of(np.array([0, 12])).tolist() == ["00z", "12z"]
    assert U.lead_bin9(np.array([1.0, 8.0])).tolist() == [1, 9]


def test_kit_selfchecks_import():
    import b24_ur7_sigma_cov, b25_ur1_tailcal, b26_ur2_stack, b27_ur3_gridpoint, b29_ur5_calm_window   # noqa: F401,E401
    import b30_ur6_tropopause, b31_ur8_control, b32_ur9_il207b_seed2, b33_ur10_radar_t, b35_ur12_beta_signal   # noqa: F401,E401
    import b28_ur4_first10 as b28
    b28._selfcheck()


def test_opendata_assembled_file_feeds_the_shipped_profile_builder(tmp_path):
    """ur15_opendata.assemble writes the WB2 layout; modeF.forecast_profiles (the rows' own builder) must read it."""
    import xarray as xr
    import ur15_opendata as O
    from tempest.forecast import modeF
    root = tmp_path / "od"
    (root / "parts").mkdir(parents=True)
    la, lo = np.array([33.0, 32.6]), np.array([-106.8, -106.4])
    z_std = np.array([111, 762, 1457, 3012, 5574, 9164, 10363, 11784, 20576.0])
    for step in (24, 72):
        t = np.stack([np.full((2, 2), 288.0 - 6.5 * z / 1000) for z in z_std]).astype(np.float32)
        np.savez(root / "parts" / f"2023060100_{step:03d}.npz", lat=la, lon=lo, t=t, u=np.full_like(t, 10.0), v=np.zeros_like(t), q=np.full_like(t, 0.002),
                 gh=np.stack([np.full((2, 2), z) for z in z_std]).astype(np.float32), u10=np.full((2, 2), 4.0, np.float32), v10=np.zeros((2, 2), np.float32),
                 t2m=np.full((2, 2), 290.0, np.float32))
    out = O.assemble(str(root), "202306", 0, [24, 72])
    h = xr.open_dataset(out).load()
    assert h["t"].dims == ("time", "prediction_timedelta", "level", "latitude", "longitude") and (h.longitude.values > 180).all()
    prof = modeF.forecast_profiles(h, np.array([0, 0]), np.array([0, 1]), np.array([0, 1]), np.array([0, 1]), np.full(2, 1200.0 * 9.80665))
    u = np.asarray(prof["u"])
    assert u.shape == (2, len(HEIGHTS)) and np.allclose(u[:, np.asarray(HEIGHTS) > 2000], 10.0, atol=0.01)
    assert O.ranges([dict(_offset=0, _length=4), dict(_offset=4, _length=4)]) == [(0, 7)]
