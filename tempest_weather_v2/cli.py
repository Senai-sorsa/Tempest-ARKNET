"""The `tempest` command line (spec I-9, P-3, P-11). It mirrors the Python API; `python -m tempest_weather_v2 ...` runs the same code.

    tempest weather spaceport_america "2027-06-16 10:00" [--all] [--percentile 10 50 90] [--marginal] [--format ras|openrocket|openrocket-csv] [--units si|us]
    tempest weather 32.99 -106.97 "2027-06-16 09:00-13:00" --all
    tempest weather midland --likely "2027-06-16 10:00" --earliest 08:00 --latest "2027-06-17 16:00"
    tempest distribution midland "2027-06-16 10:00" wind_speed temperature
    tempest couple midland "2027-06-16 10:00" temperature wind_speed --method t_copula --draw 1000 --out draws.csv
    tempest atmospheres spaceport_america "2027-06-16 10:00" --n 1000 --out june16.tempest
    tempest atmospheres spaceport_america "2027-06-16 10:00" --percentile 90 --format openrocket-csv --out p90_profile.csv
    tempest variables | sites | doctor | selftest [--update]
Quiet by default; --verbose prints what happened (elevation source, conversions, timings) to stderr. Expected errors give one helpful line, not a traceback (--debug shows the traceback).
"""
import argparse
import json
import os
import platform
import sys
import time

__all__ = ["main"]

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "selftest_golden.json")
SELFTEST_QUERY = ("spaceport_america", "2027-06-16 10:00")


def _isnum(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def _split_place(tokens):
    """['spaceport_america', 'when'] / ['32.99', '-106.97', 'when'] / ['midland'] -> (place args, remaining tokens)."""
    if len(tokens) >= 2 and _isnum(tokens[0]) and _isnum(tokens[1]):
        return (float(tokens[0]), float(tokens[1])), tokens[2:]
    if tokens:
        return (tokens[0],), tokens[1:]
    raise ValueError("give a place: a site name (see `tempest sites`) or LAT LON")


def _build_launch(a, rest):
    from tempest_weather_v2 import Launch, Window
    place, extra = _split_place(rest)
    if a.likely or a.earliest or a.latest:
        if extra:
            raise ValueError("give the time either as one argument or with --likely/--earliest/--latest, not both")
        when = Window(a.likely, earliest=a.earliest, latest=a.latest, exclude=a.exclude or ())
    else:
        if not extra:
            raise ValueError("give a time, e.g. \"2027-06-16 10:00\" or \"2027-06-16 09:00-13:00\"")
        when = Window(extra[0], exclude=a.exclude) if a.exclude else extra[0]
    kw = dict(units=a.units, seed=a.seed, offline=a.offline, verbose=a.verbose, n=a.n)
    if a.elevation:
        kw["elevation"] = a.elevation
    if a.tz:
        kw["tz"] = a.tz
    if a.mode:
        kw["mode"] = a.mode
    L = Launch(*place, when, **kw)
    return L.observe_metar(a.metar) if getattr(a, "metar", None) else L


def _common(p):
    p.add_argument("--units", choices=["us", "si"], default="us")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, default=1024, help="atmospheres in the internal pool (default 1024)")
    p.add_argument("--elevation", help="pad elevation, e.g. '4600 ft' or '1402 m' (default: the site registry, else looked up)")
    p.add_argument("--tz", help="IANA time zone for local clock times (default: the site's)")
    p.add_argument("--mode", choices=["past", "forecast", "ai"], help="force a mode (default: automatic)")
    p.add_argument("--likely"), p.add_argument("--earliest"), p.add_argument("--latest")
    p.add_argument("--exclude", nargs="*", help="cut-out hours, e.g. 12:00-14:00 or '2027-06-18 09:00-10:00'")
    p.add_argument("--metar", help="condition on a METAR report, e.g. \"KTCS 241553Z 19002KT 10SM CLR 23/12 A3012\" (wind, temperature, altimeter)")
    p.add_argument("--offline", action="store_true", help="never touch the network")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--debug", action="store_true", help="show tracebacks")


def _parser():
    ap = argparse.ArgumentParser(prog="tempest", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("weather", help="launch-site numbers for RASAero / OpenRocket")
    w.add_argument("rest", nargs="*", metavar="PLACE WHEN")
    _common(w)
    w.add_argument("--all", action="store_true")
    w.add_argument("--percentile", nargs="+", type=float)
    w.add_argument("--by", default="wind_speed")
    w.add_argument("--marginal", action="store_true")
    w.add_argument("--ras-profiles", action="store_true")
    w.add_argument("--format", choices=["table", "ras", "openrocket", "json"], default="table")
    d = sub.add_parser("distribution", help="best-fit distribution per parameter")
    d.add_argument("rest", nargs="*", metavar="PLACE WHEN VARIABLE...")
    _common(d)
    d.add_argument("--spread", choices=["full", "typical"], default="full")
    c = sub.add_parser("couple", help="joint draws of chosen parameters")
    c.add_argument("rest", nargs="*", metavar="PLACE WHEN VARIABLE...")
    _common(c)
    c.add_argument("--method", choices=["whole_sample", "gaussian_copula", "t_copula"], default="whole_sample")
    c.add_argument("--draw", type=int, default=1000)
    c.add_argument("--out")
    at = sub.add_parser("atmospheres", help="full vertical atmospheres: save the pool or export one profile")
    at.add_argument("rest", nargs="*", metavar="PLACE WHEN")
    _common(at)
    at.add_argument("--percentile", type=float, help="export the atmosphere nearest to this percentile of --by (needs --format openrocket-csv)")
    at.add_argument("--by", default="wind_speed")
    at.add_argument("--format", choices=["tempest", "openrocket-csv"], default="tempest")
    at.add_argument("--out", required=True)
    sub.add_parser("variables", help="plain names and units")
    sub.add_parser("sites", help="known launch sites")
    sub.add_parser("doctor", help="check the installation and print the fix for any problem").add_argument("--offline", action="store_true")
    st = sub.add_parser("selftest", help="run a pinned query and compare with the stored reference")
    st.add_argument("--update", action="store_true", help="rewrite the reference from this machine")
    return ap


def _split_variables(rest):
    place, extra = _split_place(rest)
    if not extra:
        raise ValueError("give a time and at least one variable")
    return place, extra[0], extra[1:]


def cmd_weather(a):
    L = _build_launch(a, a.rest)
    kw = dict(all=a.all, by=a.by, marginal=a.marginal)
    r = L.weather(percentile=(None if not a.percentile else (a.percentile if len(a.percentile) > 1 else a.percentile[0])), ras_profiles=a.ras_profiles, **kw)
    rs = r if isinstance(r, list) else [r]
    for x in rs:
        if a.format == "ras":
            print(x.to_ras())
        elif a.format == "openrocket":
            print(x.to_openrocket())
        elif a.format == "json":
            print(json.dumps(x.to_dict(), indent=1))
        else:
            print(x)
        print()
    if a.verbose:
        pv = L.provenance
        print(f"[verbose] elevation source {pv['elevation_source']}; modes {pv['modes']}; local time {L.local_time_note}", file=sys.stderr)


def cmd_distribution(a):
    place, when, variables = _split_variables(a.rest)
    L = _build_launch(a, list(map(str, place)) + [when])
    out = L.distribution(variables, spread=a.spread)
    for k, r in out.items():
        q = r["quantiles_display"]
        print(f"{k} [{r['units']}]  fit: {r['type'] or 'none'}{'' if r['fit_ok'] else ' (tail check failed: use the quantile table)'}  params {r['params']}")
        print("   " + "  ".join(f"p{int(p * 100)}={v:.3g}" for p, v in q.items()))


def cmd_couple(a):
    place, when, variables = _split_variables(a.rest)
    L = _build_launch(a, list(map(str, place)) + [when])
    c = L.couple(variables, method=a.method)
    x = c.draw(a.draw)
    head = ",".join(f"{n} [{c.display_units[n]}]" for n in c.names)
    from tempest_weather_v2 import names
    cols = [names.to_units(n, x[:, j], a.units) for j, n in enumerate(c.names)]
    import numpy as np
    arr = np.stack(cols, 1)
    if a.out:
        np.savetxt(a.out, arr, delimiter=",", header=head, comments="", fmt="%.6g")
        print(f"wrote {len(arr)} draws to {a.out} ({a.method}{', nu=%g' % c.nu if c.nu else ''}){' flags: ' + ', '.join(c.flags) if c.flags else ''}")
    else:
        print(head)
        for row in arr[:10]:
            print(",".join(f"{v:.5g}" for v in row))
        print(f"... {len(arr)} draws ({a.method})")


def cmd_atmospheres(a):
    L = _build_launch(a, a.rest)
    if a.format == "openrocket-csv":
        import numpy as np
        from tempest_weather_v2 import weather_calc as W
        s = L._ensure_pool()["samples"]
        d = L._derive(s)
        if a.by not in d or a.by.startswith("_"):
            raise ValueError(f"--by must be a per-sample numeric field, not {a.by!r}")
        p = 50.0 if a.percentile is None else a.percentile
        k = int(np.argmin(np.abs(d[a.by] - np.percentile(d[a.by], p))))
        atm = L.atmospheres()[k]
        atm.to_openrocket_csv(a.out)
        print(f"wrote atmosphere {k} (nearest to the {p:g}th percentile of {a.by}) to {a.out}")
    else:
        print(f"wrote {L.save(a.out)}")


def cmd_variables(a):
    from tempest_weather_v2 import names
    print(f"{'name':<22}{'US unit':<14}{'SI unit':<12}meaning")
    for k, (desc, kind, si, us) in names.VARIABLES.items():
        print(f"{k:<22}{names.unit_label(k, 'us'):<14}{names.unit_label(k, 'si'):<12}{desc}")


def cmd_sites(a):
    from tempest_weather_v2 import sites
    print(f"{'site':<20}{'lat':>9}{'lon':>10}{'elev (m)':>10}  {'time zone':<20}{'decl (deg)':>10}  source")
    for s in sites.load_sites().values():
        print(f"{s.name:<20}{s.lat:>9.3f}{s.lon:>10.3f}{(s.elevation_m if s.elevation_m is not None else float('nan')):>10.1f}  {s.tz or '?':<20}{s.declination():>10.1f}  {s.source}")


def cmd_doctor(a):
    problems = []
    ok = lambda msg: print(f"  ok    {msg}")
    bad = lambda msg, fix: (print(f"  FIX   {msg}\n        -> {fix}"), problems.append(msg))
    print("tempest doctor")
    v = sys.version_info
    ok(f"Python {v.major}.{v.minor}.{v.micro}") if v >= (3, 10) else bad(f"Python {v.major}.{v.minor} is too old", "install Python 3.10 or newer")
    try:
        import numpy as np
        ok(f"numpy {np.__version__}") if tuple(int(x) for x in np.__version__.split(".")[:2]) >= (1, 26) else bad(f"numpy {np.__version__} is older than 1.26", "pip install -U numpy")
    except ImportError:
        bad("numpy is missing", "pip install numpy")
    try:
        from tempest_weather_v2.timeutil import get_zone
        get_zone("America/Denver")
        ok("time zones (tzdata)")
    except Exception as e:   # noqa: BLE001
        bad(f"time zones unavailable ({e})", "pip install tzdata")
    try:
        from tempest_weather import api
        m = api._assets()["manifest"]
        ok(f"model assets verified (area lat {m['area']['lat']}, lon {m['area']['lon']})")
    except Exception as e:   # noqa: BLE001
        bad(f"model assets problem: {str(e)[:120]}", "copy or reinstall the tempest_weather/assets folder")
    try:
        from tempest_weather_v2 import _files
        d = _files.cache_dir()
        probe = os.path.join(d, ".doctor")
        _files.atomic_write(probe, "x")
        os.remove(probe)
        ok(f"cache folder writable ({d})")
    except OSError as e:
        bad(f"cache folder not writable ({e})", "set TEMPEST_CACHE to a folder you can write to")
    if a.offline:
        ok("network check skipped (--offline)")
    else:
        from tempest_weather_v2 import _net
        try:
            t0 = time.time()
            _net.fetch("https://api.open-meteo.com/v1/elevation?latitude=32.99&longitude=-106.97", service="open-meteo", retries=0, timeout=5)
            ok(f"network reachable ({time.time() - t0:.1f} s)")
        except Exception as e:   # noqa: BLE001
            print(f"  note  network not reachable ({str(e)[:80]}): elevation falls back to the site registry or the offline DEM, forecasts are unavailable")
    print("all good" if not problems else f"{len(problems)} problem(s) found")
    return 0 if not problems else 1


def _selftest_values():
    from tempest_weather_v2 import Launch
    L = Launch(SELFTEST_QUERY[0], SELFTEST_QUERY[1], mode="ai", seed=0, n=512)
    r = L.weather(all=True)
    return {k: round(float(v), 6) for k, v in r.to_dict(units="si").items()}


def cmd_selftest(a):
    vals = _selftest_values()
    if a.update:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(dict(query=SELFTEST_QUERY, values=vals), f, indent=1)
        print(f"reference written to {GOLDEN}")
        return 0
    if not os.path.exists(GOLDEN):
        print("no reference file yet: run `tempest selftest --update` once on a machine you trust")
        return 1
    ref = json.load(open(GOLDEN, encoding="utf-8"))["values"]
    bad = {k: (ref[k], vals.get(k)) for k in ref if vals.get(k) is None or abs(vals[k] - ref[k]) > 1e-3 * max(1.0, abs(ref[k]))}
    if bad:
        print("selftest FAILED:")
        for k, (r, v) in bad.items():
            print(f"  {k}: reference {r}, now {v}")
        return 1
    print(f"selftest ok ({len(ref)} values within 0.1 % of the reference)")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = _parser().parse_args(argv)
    cmds = dict(weather=cmd_weather, distribution=cmd_distribution, couple=cmd_couple, atmospheres=cmd_atmospheres, variables=cmd_variables, sites=cmd_sites, doctor=cmd_doctor, selftest=cmd_selftest)
    try:
        rc = cmds[a.cmd](a)
        return int(rc or 0)
    except KeyboardInterrupt:
        return 130
    except Exception as e:   # noqa: BLE001
        from tempest_weather_v2.timeutil import WindowError
        expected = (WindowError, KeyError, ValueError, FileNotFoundError, NotImplementedError)
        if getattr(a, "debug", False) or not isinstance(e, expected):
            if getattr(a, "debug", False):
                raise
            print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
