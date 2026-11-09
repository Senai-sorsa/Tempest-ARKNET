"""Terminal use:

    python -m tempest_weather atmosphere --lat 32.99 --lon -106.97 --when "2027-06-16 09:00" [--percentile 15 50 85] [--extra gust10 rho_sfc ...] [--format text|toml|json]
    python -m tempest_weather values --lat 32.99 --lon -106.97 --when "2027-06-16 09:00" --vars t2m_c sp wind_speed@100
    python -m tempest_weather variables

`atmosphere` prints one block per percentile of the worst-to-best order (0 = worst day, 100 = best); default 15, 50 and 85.
"""
import argparse
import sys

from tempest_weather import api, outputs, registry


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tempest_weather", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("atmosphere", "values"):
        p = sub.add_parser(name)
        p.add_argument("--lat", type=float, required=True)
        p.add_argument("--lon", type=float, required=True)
        p.add_argument("--when", required=True, help='"2027-06-16 09:00" is local solar time; add an offset (+00:00) for an exact instant')
        p.add_argument("--elevation", type=float, help="launch site elevation in metres (default: the grid cell's); temperature and pressure are moved to it")
        p.add_argument("--n", type=int, default=1024)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--mode", choices=["past", "recent", "week", "medium", "ai"])
        p.add_argument("--era5-store", help="local ERA5 profiles zarr for past dates (or set TEMPEST_ERA5_STORE)")
        p.add_argument("--assets", help="folder with model.npz etc. (default: the assets folder next to this file)")
        if name == "atmosphere":
            p.add_argument("--percentile", type=float, nargs="+", default=[15, 50, 85])
            p.add_argument("--extra", nargs="*", default=[], help="extra single values, e.g. gust10 rho_sfc wind_speed@1000")
            p.add_argument("--format", choices=["text", "toml", "json"], default="text")
        else:
            p.add_argument("--vars", nargs="+", required=True)
    sub.add_parser("variables")
    a = ap.parse_args(argv)
    if a.cmd == "variables":
        print("\n".join(registry.valid_names()))
        return 0
    try:
        if a.cmd == "values":
            r = api.values(a.lat, a.lon, a.when, a.vars, mode=a.mode, n=a.n, seed=a.seed, assets=a.assets, elevation=a.elevation, era5_store=a.era5_store)
            for k, v in r["values"].items():
                print(f"{k:<24} {v:12.4f} {r['units'][k]}")
            print(f"# mode {r['mode']}, quality {r['quality']}, valid {r['valid_utc']} UTC", file=sys.stderr)
            return 0
        res = api.atmosphere(a.lat, a.lon, a.when, a.percentile, a.extra, a.n, a.seed, mode=a.mode, assets=a.assets, elevation=a.elevation, era5_store=a.era5_store)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for d in res:
        m = d["meta"]
        label = f"percentile {m['percentile']:g} of worst-to-best flight conditions (flight score {m['flight_score']:.2f}; mode {m['mode']}; {', '.join(m['quality'])})"
        if a.format == "text":
            print(outputs.to_text(d, label))
        elif a.format == "toml":
            print(f"# {label}\n" + outputs.to_toml(d, m["source"], a.when, ""))
        else:
            print(outputs.to_json(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
