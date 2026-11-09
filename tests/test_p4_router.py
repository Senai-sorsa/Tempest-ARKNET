"""Router: modes by lead, smooth weights, mixtures keep whole samples."""
import numpy as np

from tempest.forecast import router as r


def test_modes_by_lead():
    assert [r.mode(x) for x in (-30, -6, -3, 0.0, 1, 7, 8, 15, 16, 46, 47, 400)] == ["P", "P", "P0", "P0", "F", "F", "F2", "F2", "M", "M", "C", "C"]


def test_weights_are_monotone_continuous_and_bounded():
    lead = np.linspace(0, 60, 601)
    wc = r.climate_weight(lead)
    we = r.ensemble_weight(lead)
    assert (np.diff(wc) >= -1e-12).all() and (np.diff(we) <= 1e-12).all()
    assert wc.min() >= 0 and wc.max() <= 1 and we.min() >= 0 and we.max() <= 1
    assert np.abs(np.diff(wc)).max() < 0.04 and np.abs(np.diff(we)).max() < 0.04   # no jumps between neighbouring leads
    assert r.ensemble_weight(9.9) == 1.0 and r.ensemble_weight(15.0) == 0.0 and r.climate_weight(50.0) == 1.0


def test_mix_takes_whole_rows_from_one_side():
    rng = np.random.default_rng(0)
    a, b = np.zeros((1000, 5)), np.ones((1000, 5))
    x = r.mix(rng, a, b, 0.3)
    assert set(np.unique(x)) == {0.0, 1.0} and (x.min(1) == x.max(1)).all()      # a row is never half and half
    assert abs(x[:, 0].mean() - 0.3) < 0.05
