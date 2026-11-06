"""configs/region.toml: the pilot values the code used to hard-code, and the point-index rule of the profile stores."""
import numpy as np

from tempest import region


def test_default_is_the_pilot_box_and_matches_the_store_layout():
    r = region.load()
    assert (r.n_lat, r.n_lon, r.n_points) == (13, 29, 377) and r.era5_lon360 == (252.0, 259.0)
    assert r.point_index(34.0, -108.0) == 0 and r.point_index(31.0, -101.0) == 376
    assert r.point_index(33.0, -106.0) == int(np.round((34 - 33.0) / 0.25)) * 29 + int(np.round((-106 + 108) / 0.25))       # the formula the scripts used
    lat, lon = r.grid()
    assert len(lat) == 377 and lat[0] == 34.0 and lon[0] == -108.0 and lon[28] == -101.0 and lat[29] == 33.75
    assert r.contains(32.9, -106.9) and not r.contains(39.7, -105.0)
    assert list(r.asos) == ["MAF", "TCS"] and "USM00072364" in r.stations


def test_another_box_changes_everything_consistently(tmp_path):
    f = tmp_path / "r.toml"
    f.write_text('name="north"\nlat_north=40.0\nlat_south=30.0\nlon_west=-110.0\nlon_east=-100.0\nstep=0.5\n')
    r = region.load(str(f))
    assert (r.n_lat, r.n_lon, r.n_points) == (21, 21, 441) and r.era5_lon360 == (250.0, 260.0)
    assert r.point_index(40.0, -110.0) == 0 and r.point_index(30.0, -100.0) == 440


def test_tool_picks_the_asset_set_by_location(tmp_path):
    import json
    from tempest_weather import api
    for name, lat, lon in (("assets", [31.0, 34.0], [-108.0, -101.0]), ("assets_denver", [38.0, 40.0], [-106.0, -104.0]), ("not_assets", [0.0, 90.0], [-180.0, 180.0])):
        d = tmp_path / name
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"area": {"lat": lat, "lon": lon}}))
    assert api.regions(str(tmp_path)).keys() == {"assets", "assets_denver"}                 # only folders called assets*
    assert api.region_assets(32.9, -106.9, str(tmp_path)).endswith("assets")
    assert api.region_assets(39.7, -105.0, str(tmp_path)).endswith("assets_denver")
    assert api.region_assets(45.0, -100.0, str(tmp_path)) is None
