"""R1 roughness (builder, lookup, fallback, Launch wiring) and the tempest command line."""
import json

import numpy as np
import pytest

from tempest_weather_v2 import Launch, roughness as R
from tempest_weather_v2.cli import main


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))


# ---------------------------------------------------------------- roughness
def test_table_has_sensible_classes():
    t = R.load_table()
    assert t[11][2] < t[52][2] < t[42][2] and t[82][0] < t[82][2]                    # water < scrub < forest; crops rougher in summer than winter


def _half_water_half_scrub(n=40):
    lc = np.full((n, n), 52)
    lc[:, : n // 2] = 11                                                             # west half water, east half scrub
    return lc


def test_sector_map_sees_the_upwind_surface():
    codes = R.build_sector_map(_half_water_half_scrub(), 250.0, R.load_table())
    m = R.RoughnessMap(codes, 33.0, -107.0, 0.00225, 0.00268)
    i, j = 20, 21                                                                    # one cell east of the shore
    lat, lon = m.lat0 - i * m.dlat, m.lon0 + j * m.dlon
    from_west = m.z0(lat, lon, 270.0, 7)                                             # wind from the west: upwind is water
    from_east = m.z0(lat, lon, 90.0, 7)                                              # wind from the east: upwind is scrub
    assert from_west < 0.02 and from_east > 0.05 and from_east > 5 * from_west
    far_east = m.z0(m.lat0 - 20 * m.dlat, m.lon0 + 38 * m.dlon, 270.0, 7)            # deep in the scrub, whatever the direction
    assert far_east == pytest.approx(0.1, rel=0.2)
    assert np.isnan(m.z0(10.0, 10.0, 90.0, 7)) and m.covers(lat, lon) and not m.covers(10.0, 10.0)
    arr = m.z0(lat, lon, np.array([270.0, 90.0, 0.0]), 7)
    assert arr.shape == (3,) and arr[0] < arr[1]


def test_season_and_save_load(tmp_path):
    lc = np.full((20, 20), 82)                                                       # cultivated crops everywhere
    m = R.RoughnessMap(R.build_sector_map(lc, 250.0, R.load_table()), 33.0, -107.0, 0.00225, 0.00268)
    lat, lon = 33.0 - 10 * 0.00225, -107.0 + 10 * 0.00268
    assert m.z0(lat, lon, 180.0, 7) > 5 * m.z0(lat, lon, 180.0, 1)                   # summer vs winter
    p = m.save(str(tmp_path / "z0.npz"))
    m2 = R.RoughnessMap.load(p)
    assert np.array_equal(m.codes, m2.codes) and m2.lat0 == m.lat0
    with pytest.raises(ValueError):
        R.RoughnessMap(np.zeros((2, 2)), 0, 0, 1, 1)
    with pytest.raises(KeyError, match="not in the z0 table"):
        R.build_sector_map(np.full((5, 5), 999), 250.0, R.load_table())
    assert R.season_of(1) == 0 and R.season_of(7) == 2 and R.season_of(12) == 0


def test_launch_uses_the_map_or_flags_the_default(monkeypatch):
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200)
    r = L.weather(all=True)
    assert r.surface_roughness_m == pytest.approx(0.03) and "z0-default-0.03" in r.flags and L.z0() == pytest.approx(0.03)
    lc = np.full((10, 10), 52)
    m = R.RoughnessMap(R.build_sector_map(lc, 250.0, R.load_table()), L.lat + 0.01, L.lon - 0.01, 0.00225, 0.00268)
    monkeypatch.setattr(R, "load_default", lambda: m)
    L2 = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200)
    r2 = L2.weather(all=True)
    assert 0.05 < r2.surface_roughness_m < 0.2 and "z0-default-0.03" not in r2.flags            # scrub in summer
    assert Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200, z0=0.005).weather(all=True).surface_roughness_m == pytest.approx(0.005)


# ---------------------------------------------------------------- command line
def run(capsys, *argv):
    rc = main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_cli_lists(capsys):
    rc, out, _ = run(capsys, "variables")
    assert rc == 0 and "wind_speed" in out and "inHg" in out
    rc, out, _ = run(capsys, "sites")
    assert rc == 0 and "spaceport_america" in out and "America/Denver" in out


def test_cli_weather_formats_and_errors(capsys):
    base = ["weather", "spaceport_america", "2027-06-16 10:00", "--mode", "ai", "--n", "300"]
    rc, out, _ = run(capsys, *base)
    assert rc == 0 and "elevation" in out and "Climate estimate" in out
    rc, out, _ = run(capsys, *base, "--format", "ras")
    assert "RASAero II launch site" in out and "(ft)" in out
    rc, out, _ = run(capsys, *base, "--format", "openrocket", "--units", "si")
    assert "Station pressure (mbar)" in out
    rc, out, _ = run(capsys, *base, "--percentile", "10", "50", "90")
    assert out.count("10:00 MDT") == 3 and "90th percentile" in out
    rc, out, _ = run(capsys, *base, "--format", "json", "--all")
    assert json.loads(out.split("\n\n")[0])["elevation"] == pytest.approx(4595.1, abs=0.5)
    rc, out, err = run(capsys, "weather", "spaceport_amerca", "2027-06-16 10:00")
    assert rc == 2 and "did you mean spaceport_america" in err and "Traceback" not in err
    rc, out, err = run(capsys, "weather", "spaceport_america")
    assert rc == 2 and "give a time" in err
    rc, out, err = run(capsys, "weather", "spaceport_america", "2027-06-16 03:00", "--mode", "ai")
    assert rc == 2 and "valid solar hours" in err
    rc, out, _ = run(capsys, "weather", "32.99", "-106.97", "2027-06-16 09:00-13:00", "--mode", "ai", "--n", "300", "--elevation", "4595 ft", "--tz", "America/Denver")
    assert rc == 0 and "uniform" in out
    rc, out, _ = run(capsys, "weather", "midland", "--likely", "2027-06-16 10:00", "--earliest", "08:00", "--latest", "2027-06-16 14:00", "--mode", "ai", "--n", "300", "--offline")
    assert rc == 0 and "triangular" in out


def test_cli_distribution_couple_atmospheres(capsys, tmp_path):
    common = ["spaceport_america", "2027-06-16 10:00", "--mode", "ai", "--n", "300"]
    rc, out, _ = run(capsys, "distribution", *common[:2], "wind_speed", "temperature", *common[2:])
    assert rc == 0 and "wind_speed [mph]" in out and "temperature [°F]" in out and "p50=" in out
    rc, out, err = run(capsys, "distribution", *common[:2], "wind_sped", *common[2:])
    assert rc == 2 and "did you mean wind_speed" in err
    csv = tmp_path / "draws.csv"
    rc, out, _ = run(capsys, "couple", *common[:2], "temperature", "wind_speed", "--method", "t_copula", "--draw", "200", "--out", str(csv), *common[2:])
    assert rc == 0 and "nu=" in out and len(csv.read_text().splitlines()) == 201 and csv.read_text().splitlines()[0].startswith("temperature [°F]")
    out_file = tmp_path / "june16.tempest"
    rc, out, _ = run(capsys, "atmospheres", *common, "--out", str(out_file))
    assert rc == 0 and out_file.exists() and len(Launch.load(str(out_file)).atmospheres(5)) == 5
    prof = tmp_path / "p90.csv"
    rc, out, _ = run(capsys, "atmospheres", *common, "--percentile", "90", "--format", "openrocket-csv", "--out", str(prof))
    assert rc == 0 and prof.read_text().startswith("altitude_m,temp_K,pressure_Pa,wind_speed_ms,wind_from_deg") and "90th percentile" in out


def test_cli_doctor_and_selftest(capsys, tmp_path, monkeypatch):
    from tempest_weather_v2 import cli
    rc, out, _ = run(capsys, "doctor", "--offline")
    assert rc == 0 and "model assets verified" in out and "all good" in out
    monkeypatch.setattr(cli, "GOLDEN", str(tmp_path / "golden.json"))
    rc, out, _ = run(capsys, "selftest")
    assert rc == 1 and "no reference file" in out
    rc, out, _ = run(capsys, "selftest", "--update")
    assert rc == 0 and (tmp_path / "golden.json").exists()
    rc, out, _ = run(capsys, "selftest")
    assert rc == 0 and "selftest ok" in out
    g = json.loads((tmp_path / "golden.json").read_text())
    g["values"]["temperature"] += 5.0
    (tmp_path / "golden.json").write_text(json.dumps(g))
    rc, out, _ = run(capsys, "selftest")
    assert rc == 1 and "FAILED" in out and "temperature" in out
