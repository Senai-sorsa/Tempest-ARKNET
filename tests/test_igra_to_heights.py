import numpy as np

from tempest.ingest.igra_to_heights import EXT_HEIGHTS, RD, heights_gph, parse, sounding
from tempest.profiles.to_heights import G0


def test_hypsometric_fills_missing_heights():
    p = np.array([100000.0, 85000, 70000, 50000])
    t = np.full(4, 250.0)
    z = 1000 + RD * 250 / G0 * np.log(1e5 / p)  # dry isothermal truth
    gph = np.array([1000.0, np.nan, z[2], np.nan])
    out = heights_gph(np.array([1, 0, 0, 0.0]), p, gph, t, np.zeros(4))
    assert np.allclose(out, z, atol=0.5)


def test_parse_and_wind_sign():
    head = "#USM00072364 2023 07 01 12 1104    3 ncdc-nws ncdc-gts  318728 -1066980"
    rows = ["21     0  87398B 1254   210B  390   145   270    50 ",
            "10    43  85000  1498B  287B   62   407   270    50 ",
            "10   547  70000  3179B  149B  115   296   270    50 "]
    (hd, a), = parse("\n".join([head] + rows))
    assert hd == head and a.shape == (3, 9) and a[0, 1] == 1 and a[1, 2] == 85000
    prof, lnp, sfc, z0 = sounding(a, EXT_HEIGHTS)
    assert z0 == 1254 and np.isclose(sfc[0], 21.0 + 273.15) and np.isclose(sfc[1], 87398)
    assert np.isclose(prof[0][0], 5.0) and abs(prof[1][0]) < 1e-5  # wind from 270 deg blows toward +u (east)
    assert np.isnan(prof[2][EXT_HEIGHTS > 2000]).all()  # nothing above the top level
