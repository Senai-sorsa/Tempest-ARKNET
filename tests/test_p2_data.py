"""Phase 2 data options: dynamic feature list, GMST without leakage, ONI hinges, dewpoint-depression humidity, ridge."""
import numpy as np
import pandas as pd
import pytest

from tempest.calibrate.station import smooth
from tempest.generator import features as feat
from tempest.generator import sample
from tempest.generator.train import load_npz
from tempest.ingest import indices


@pytest.fixture(autouse=True)
def reset_globals():
    yield
    feat.set_active(feat.BASE_FEATURES)
    sample.set_rh_target("rh")


def test_default_features_unchanged():
    f = feat.features(32.99, -106.97, 1400, 1350, np.arange(5), 9.5, 2027, np.zeros(5), 0, 5.0, -3.0)
    assert f.shape == (5, 13) and feat.FEATURES == feat.BASE_FEATURES


def test_p2_features_hinges_and_requirements():
    feat.set_active(feat.P2_FEATURES)
    oni = np.array([-1.0, 0.0, 1.5])
    with pytest.raises(ValueError):
        feat.features(33, -107, 1400, 1400, 100, 10, 2020, oni, 0, 0, 0)  # gmst and lag missing
    f = feat.features(33, -107, 1400, 1400, 100, 10, 2020, oni, 0, 0, 0, gmst=1.0, oni_lag3=0.2)
    names = feat.FEATURES
    assert "year" not in names and f.shape == (3, 16)
    assert np.allclose(f[:, names.index("oni_pos")], [0, 0, 1.5]) and np.allclose(f[:, names.index("oni_neg")], [-1, 0, 0])
    assert feat.drivers() == ["oni", "wwv", "qbo30", "qbo50", "oni_pos", "oni_neg", "oni_lag3"]


def _gm(tmp_path, extra=None):
    rows = ["Land-Ocean: Global Means", "Year," + ",".join(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) + ",J-D"]
    for y in range(1990, 2001):
        vals = [0.01 * (y - 1990) + 0.001 * m for m in range(12)]
        if extra and y == 2000:
            vals = extra
        rows.append(f"{y}," + ",".join(f"{v:.3f}" for v in vals) + ",0")
    (tmp_path / "gistemp.csv").write_text("\n".join(rows), encoding="utf-8")
    return indices.gmst_table(str(tmp_path), window=24)


def test_gmst_is_trailing_and_carries_forward(tmp_path):
    a = _gm(tmp_path)
    b = _gm(tmp_path, extra=[9.0] * 12)  # change the last year's data
    t = pd.to_datetime(["1995-06-10", "1999-12-31", "2000-01-02"])
    # a month's value uses only months before it: changing 2000 leaves 1999 and Jan 2000 unchanged
    assert np.allclose(indices.gmst_at(a, t), indices.gmst_at(b, t)[:3])
    assert indices.gmst_at(a, t)[0] < indices.gmst_at(a, t)[1]            # warming shows
    far = indices.gmst_at(a, pd.to_datetime(["2030-01-01", "2040-01-01"]))
    assert far[0] == far[1] and np.isclose(far[0], a.iloc[-1], atol=1e-6)                                  # carried forward


def test_dpd_roundtrip_and_never_above_saturation():
    t = np.linspace(205, 315, 200)
    rh = np.linspace(0.5, 100, 200)
    assert np.allclose(sample.rh_from_dpd(t, sample.dpd_from_rh(t, rh)), rh, atol=1e-6)
    wild = np.random.default_rng(0).normal(1.5, 3.0, 5000)                 # samples from a network, any value
    assert (sample.rh_from_dpd(np.full(5000, 270.0), wild) <= 100 + 1e-9).all()


def test_to_physical_rebuilds_rh_from_dpd():
    n = 44
    rng = np.random.default_rng(1)
    T = 290 - np.arange(n) * 1.2
    rh = rng.uniform(5, 95, n)
    u = rng.normal(size=n)
    prof = np.stack([u, u * 0, T, sample.dpd_from_rh(T, rh)])
    from tempest.profiles.diff import to_diff
    raw = np.concatenate([to_diff(prof).ravel(), [T[0], 87000.0, sample.dpd_from_rh(np.array(T[0]), np.array(rh[0]))]])[None]
    sample.set_rh_target("dpd")
    out = sample.to_physical(raw.astype(np.float64))[0]
    assert np.allclose(out[3 * n:4 * n], rh, atol=1e-4) and np.isclose(out[-1], rh[0], atol=1e-4)


def test_load_npz_activates_dataset_settings(tmp_path):
    n = 10
    names = feat.P2_FEATURES
    np.savez(tmp_path / "p2.npz", cond=np.zeros((n, len(names)), np.float32), target=np.zeros((n, 179), np.float32),
             year=np.zeros(n, np.int16), cond_names=np.array(names), rh_target=np.array("dpd"))
    np.savez(tmp_path / "old.npz", cond=np.zeros((n, 13), np.float32), target=np.zeros((n, 179), np.float32),
             year=np.zeros(n, np.int16), cond_names=np.array(feat.BASE_FEATURES))
    load_npz(str(tmp_path / "p2.npz"))
    assert feat.FEATURES == feat.P2_FEATURES and sample.RH_TARGET == "dpd"
    load_npz(str(tmp_path / "old.npz"))
    assert feat.FEATURES == feat.BASE_FEATURES and sample.RH_TARGET == "rh"


def test_ridge_smoother():
    x = np.sin(np.linspace(0, 3, 44)) + np.random.default_rng(0).normal(0, 0.2, 44)
    assert np.array_equal(smooth(x, 0), x)
    y = smooth(x, 10.0)
    assert np.abs(np.diff(y, 2)).mean() < np.abs(np.diff(x, 2)).mean() and abs(y.mean() - x.mean()) < 1e-9
