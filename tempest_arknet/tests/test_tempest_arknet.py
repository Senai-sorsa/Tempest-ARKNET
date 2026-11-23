"""Tests for the tempest_arknet package (mirrors dynamics/tools/weather/earthgram/tests).

    python tempest_arknet/tests/test_tempest_arknet.py      (from the Tempest-ARKNET folder)

The offline tests feed a small synthetic Tempest sample set through the wrapper. The live
tests run the real Tempest-ARKNET engine and are skipped when no asset set is present.
Exit code 1 on any failure.
"""
import math
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # Tempest-ARKNET
import tempest_arknet as ta  # noqa: E402
from tempest_arknet import __main__ as cli  # noqa: E402
from tempest_arknet import api  # noqa: E402
from tempest_weather import _core  # noqa: E402

SITE = ta.LaunchSite("West TX", lat=31.024, lon=-103.6616, elev_m=900)
H = _core.HEIGHTS.astype(float)


def raises(exc, fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def fake_atm(n=3, seed=0):
    """A standard-atmosphere-like sample set in tempest_weather's layout, runs scattered by a few K / m/s."""
    rng = np.random.default_rng(seed)
    dT, du = rng.normal(0, 2, (n, 1)), rng.normal(0, 3, (n, 1))
    T = 300.0 - 0.0065 * H + dT
    sp = np.full(n, 91_000.0)
    t2m, rh2m = T[:, 0] + 0.5, np.full(n, 30.0)
    RH = np.full((n, len(H)), 30.0)
    th = _core.thermo_column(H, T, RH, sp, t_sfc=t2m, rh_sfc=rh2m, z_sfc=SITE.elev_m)
    u = 2.0 + 0.002 * H + du
    v = np.full_like(u, -1.0)
    atm = dict(u=u, v=v, T=T, RH=RH, t2m=t2m, sp=sp, rh2m=rh2m, p=th["p"], rho=th["rho"], a=th["a"],
               w=np.zeros_like(u), gust_mu=None, gust_beta=None)
    return atm, dict(mode="ai", source="fake", quality=[])


def with_fake(fn, n=3):
    calls = []

    def fake(lat, lon, when, n=n, seed=0, **kw):
        calls.append(dict(lat=lat, lon=lon, when=when, n=n, seed=seed, **kw))
        return fake_atm(n, seed)
    with mock.patch.object(api.tw, "atmosphere_set", fake), mock.patch.object(api, "check_install", lambda: None):
        return fn(), calls


# ---------------------------------------------------------------- offline

def test_wind_direction_convention():
    d = api.wind_dir_from(np.array([0.0, -5.0, 5.0, 0.0]), np.array([-5.0, 0.0, 0.0, 5.0]))
    assert np.allclose(d, [0.0, 90.0, 270.0, 180.0])


def test_altitude_grid_and_limits():
    assert np.allclose(api._altitudes(SITE, 1900, 250), [900, 1150, 1400, 1650, 1900])
    assert api._altitudes(SITE, None, 1000)[-1] == 900 + 18_000
    assert raises(ValueError, api._altitudes, SITE, 800, 250)
    assert raises(ValueError, api._altitudes, SITE, 30_000, 250)   # above the 18 km model top
    assert raises(ValueError, api._altitudes, SITE, 2000, 0)


def test_time_is_sent_as_utc_instant():
    _, calls = with_fake(lambda: ta.profile(SITE, "2026-06-15 13:00", "America/Chicago", top_m=1900, n=3))
    assert pd.Timestamp(calls[0]["when"]) == pd.Timestamp("2026-06-15 18:00", tz="UTC")
    assert calls[0]["elevation"] == 900
    assert raises(ValueError, ta.profile, SITE, "2026-06-15 13:00")   # naive time, no tz


def test_columns_hit_model_heights_exactly():
    atm, _ = fake_atm()
    alt = SITE.elev_m + np.array([0.0, 10.0, 1000.0, 18_000.0])
    c = api._columns(atm, SITE.elev_m, alt)
    assert np.allclose(c["temp"][:, 0], atm["t2m"]) and np.allclose(c["p"][:, 0], atm["sp"])
    assert np.allclose(c["u"][:, 0], atm["u"][:, 0])                 # wind held at its 10 m value below 10 m
    i1000 = int(np.flatnonzero(H == 1000)[0])
    assert np.allclose(c["temp"][:, 2], atm["T"][:, i1000]) and np.allclose(c["p"][:, 2], atm["p"][:, i1000])
    assert np.allclose(c["rho"][:, 3], atm["rho"][:, -1])
    # rho may rise from 0 to 10 m (2 m air warmer than 10 m air on a sunny afternoon), so only above that
    assert (np.diff(c["p"], axis=1) < 0).all() and (np.diff(c["rho"][:, 1:], axis=1) < 0).all()


def test_profile_mean_and_sigma():
    p, _ = with_fake(lambda: ta.profile(SITE, "2026-06-15 18:00", "UTC", top_m=1900, n=3))
    m = p.mean
    assert len(m) == 5 and np.allclose(m["alt_m"], [900, 1150, 1400, 1650, 1900])
    assert (np.diff(m["p"]) < 0).all() and (np.diff(m["rho"]) < 0).all() and (m["temp_sd"] > 0).all()
    for k in (-3, 0, 2):
        s = p.sigma(k)
        assert np.allclose(s["temp"], m["temp"] + k * m["temp_sd"])
        assert np.allclose(s["p"], m["p"] + k * m["p_sd"])
        assert (s["speed"] >= 0).all()
    mid = p.at(1025.0)
    assert abs(mid["temp"] - (m["temp"][0] + m["temp"][1]) / 2) < 1e-9
    assert raises(ValueError, p.at, 5000)
    assert p.info["mode"] == "ai"


def test_monte_carlo_views():
    mc, _ = with_fake(lambda: ta.monte_carlo(SITE, "2026-06-15 18:00", "UTC", n=3, top_m=1900))
    assert mc.n == 3 and len(mc.runs) == 15 and mc.values("temp").shape == (3, 5)
    assert np.allclose(mc.runs["speed"], np.hypot(mc.runs["u"], mc.runs["v"]))
    assert np.allclose(mc.mean["temp"], mc.values("temp").mean(0))   # the mean is of the same runs
    r2 = mc.run_profile(2)
    assert len(r2) == 5 and np.allclose(r2["temp"], mc.values("temp")[2])
    assert raises(IndexError, mc.run_profile, 3)
    q = mc.percentiles([5, 50, 95], cols=("temp", "speed"))
    assert list(q.columns) == ["alt_m", "temp_p5", "temp_p50", "temp_p95", "speed_p5", "speed_p50", "speed_p95"]
    assert (q["temp_p5"] <= q["temp_p50"]).all() and (q["temp_p50"] <= q["temp_p95"]).all()
    assert np.allclose(q["temp_p95"], mc.runs.groupby("alt_m")["temp"].quantile(0.95).to_numpy())
    assert raises(ValueError, ta.monte_carlo, SITE, "2026-06-15 18:00", "UTC", n=0)


def test_openrocket_export():
    p, _ = with_fake(lambda: ta.profile(SITE, "2026-06-15 18:00", "UTC", top_m=1900, n=3))
    mc, _ = with_fake(lambda: ta.monte_carlo(SITE, "2026-06-15 18:00", "UTC", n=3, top_m=1900))
    with tempfile.TemporaryDirectory() as d:
        w = pd.read_csv(ta.openrocket_wind_csv(p.mean, Path(d) / "w.csv"))
        assert list(w.columns) == ["altitude", "speed", "direction", "stddev"] and len(w) == 5
        assert w["direction"].between(0, 360).all() and (w["stddev"] > 0).all()
        assert (pd.read_csv(ta.openrocket_wind_csv(mc.run_profile(0), Path(d) / "r.csv"))["stddev"] == 0).all()


def test_cli_writes_csvs():
    with tempfile.TemporaryDirectory() as d:
        argv = ["--lat", "31.024", "--lon", "-103.6616", "--elev", "900", "--time", "2026-06-15 13:00",
                "--tz", "America/Chicago", "--top", "3000", "--mc", "3", "--out", d, "--csv", f"{d}/t.csv"]
        rc, _ = with_fake(lambda: cli.main(argv))
        assert rc == 0
        assert {"mean_profile.csv", "openrocket_wind.csv", "monte_carlo_runs.csv", "percentiles.csv", "t.csv"} <= {
            f.name for f in Path(d).iterdir()}
        t = pd.read_csv(Path(d) / "t.csv")
        assert list(t.columns) == ["alt_m", "alt_ft", "temp", "temp_sd", "p", "rho", "speed", "speed_sd", "speed_mph", "dir_from"]


def test_missing_install_is_reported():
    with mock.patch.object(api.tw, "regions", lambda root=None: {}):
        assert not ta.is_installed()
        assert raises(ta.TempestNotFound, ta.profile, SITE, "2026-06-15 18:00", "UTC")


# ---------------------------------------------------------------- live (needs the Tempest assets)

def live(fn):
    fn.live = True
    return fn


@live
def test_live_profile_is_physical():
    m = ta.profile(SITE, "2027-06-15 13:00", "America/Chicago", top_m=15_000, step_m=500, n=400).mean
    assert m["alt_m"].iloc[0] == 900 and m["alt_m"].iloc[-1] == 14_900
    assert 85_000 < m["p"].iloc[0] < 95_000          # ~91 kPa at 900 m
    assert 290 < m["temp"].iloc[0] < 320             # June afternoon, West Texas
    assert (np.diff(m["p"]) < 0).all() and (np.diff(m["rho"]) < 0).all()
    trop = m[m["alt_m"].between(2000, 11_000)]
    assert (np.diff(trop["temp"]) < 0).all()         # cooling through the troposphere
    assert (m["temp_sd"] > 0).all() and (m["speed_sd"] > 0).all()


@live
def test_live_season():
    b = ta.profile(SITE, "2027-06-15 13:00", "America/Chicago", top_m=2000, n=400).mean
    d = ta.profile(SITE, "2027-01-15 13:00", "America/Chicago", top_m=2000, n=400).mean
    assert b["temp"].iloc[0] - d["temp"].iloc[0] > 10  # June warmer than January


@live
def test_live_launch_window():
    w = ta.launch_window(SITE, "2027-06-15", "America/Chicago", hours=[7, 13], top_m=1900, n=200)
    assert list(w.columns[:2]) == ["local_time", "alt_m"] and len(w) == 2 * 5
    first = w[w["alt_m"] == 900].set_index("local_time")["temp"]
    assert first.iloc[1] - first.iloc[0] > 3  # afternoon warmer than morning


@live
def test_live_monte_carlo_stats_and_seed():
    kw = dict(n=300, top_m=5000, step_m=500)
    a = ta.monte_carlo(SITE, "2027-06-15 13:00", "America/Chicago", seed=42, **kw)
    a2 = ta.monte_carlo(SITE, "2027-06-15 13:00", "America/Chicago", seed=42, **kw)
    b = ta.monte_carlo(SITE, "2027-06-15 13:00", "America/Chicago", seed=43, **kw)
    assert a.n == 300 and np.allclose(a.runs, a2.runs) and not np.allclose(a.runs, b.runs)
    for c in ("temp", "u", "v"):
        assert np.allclose(a.values(c).std(0, ddof=1), a.mean[f"{c}_sd"])
        assert abs(a.values(c).mean() - a.mean[c].mean()) < 1e-9 * max(1, abs(a.mean[c].mean())) + 1e-9
    assert math.isfinite(a.runs["w"].iloc[0])


@live
def test_live_outside_region_raises():
    assert raises(ValueError, ta.profile, ta.LaunchSite("College Station", 30.7875, -96.593, 90),
                  "2026-11-22 13:00", "UTC", top_m=1000, n=10)


def main() -> int:
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    installed = ta.is_installed()
    failed = skipped = 0
    for name, fn in tests:
        if getattr(fn, "live", False) and not installed:
            print(f"SKIP {name} (Tempest assets not present)")
            skipped += 1
            continue
        try:
            fn()
            print(f"ok   {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
