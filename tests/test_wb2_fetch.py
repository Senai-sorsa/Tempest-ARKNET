"""WB2 fetch: the pieces that do not need the network (variable maps, defaults)."""
from tempest.ingest import wb2_fetch as W


def test_maps_and_box():
    assert set(W.UPPER.values()) == {"u", "v", "t", "q", "z"} and set(W.SURF.values()) == {"u10", "v10", "t2m", "sp"}
    assert W.LAT[0] < W.LAT[1] and 252.0 <= W.LON[0] < W.LON[1] <= 259.0                   # 108 W = 252 E, 101 W = 259 E
