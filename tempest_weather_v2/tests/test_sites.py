"""Site registry: built-in sites, aliases, typo help, user sites, time-zone guess, declination fallback."""
import pytest

from tempest_weather_v2 import sites as S


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))


def test_builtin_sites_aliases_and_normalised_names():
    sa = S.get_site("spaceport_america")
    assert (sa.lat, sa.lon, sa.tz) == (32.99, -106.97, "America/Denver") and abs(sa.elevation_m - 1400.6) < 1e-9
    assert S.get_site("Spaceport America") is not None and S.get_site("IREC").name == "spaceport_america"
    assert S.get_site("midland").tz == "America/Chicago"
    with pytest.raises(KeyError, match="did you mean spaceport_america"):
        S.get_site("spaceport_amerca")
    with pytest.raises(KeyError, match="known sites"):
        S.get_site("nowhere")


def test_user_site_is_stored_and_overrides():
    s = S.add_site("My Pad", 32.5, -105.5, elevation="4600 ft")
    assert s.name == "my_pad" and abs(s.elevation_m - 1402.08) < 1e-6 and s.tz == "America/Denver"
    assert S.get_site("my_pad").source == "user"
    S.add_site("midland", 31.9, -102.2, elevation=870.0, tz="America/Chicago")
    assert S.get_site("midland").elevation_m == 870.0 and S.get_site("midland").source == "user"
    s2 = S.add_site("looked_up", 33.0, -107.0, lookup=lambda a, b: 1234.5)
    assert s2.elevation_m == 1234.5


def test_tz_guess_and_declination_fallback():
    assert S.guess_tz(33.0, -107.0) == "America/Denver" and S.guess_tz(31.9, -102.2) == "America/Chicago"
    assert S.guess_tz(34.0, -118.0) == "America/Los_Angeles" and S.guess_tz(40.0, -74.0) == "America/New_York"
    assert S.guess_tz(51.5, -0.1) == "UTC" and S.guess_tz(35.0, 139.0) == "Etc/GMT-9"
    assert S.get_site("spaceport_america").declination() == 7.9
    assert abs(S.Site("x", 32.99, -106.97).declination(2026.9) - 8.0) < 3.0      # computed when not stored
