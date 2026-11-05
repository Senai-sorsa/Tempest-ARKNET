"""Scope check (user request 2026-11-05): where and when does the standalone tool answer, and does it fail clearly where it cannot?
    PYTHONPATH=. python scripts/check_scope.py
Locations: a 5 x 5 grid over the trained box, its four corners, and cities outside it. Dates: tomorrow-ish to the year 2100, and the past without an ERA5 store.
Hours: every solar hour 0-23. Prints one line per case and a summary; nothing is fitted or written.
"""
import time
import warnings

import numpy as np

import tempest_weather as tw

warnings.filterwarnings("ignore")
VARS = ["T@2000", "u@5000", "v@5000", "RH@3000", "wind_speed@10000", "p@10", "rho@1000"]
NOW = "2026-11-05T00:00"
rows = []


def case(name, lat, lon, when, **kw):
    t0 = time.time()
    try:
        out = tw.values(lat, lon, when, VARS, n=398, now=NOW, **kw)
        v = np.array(list(out["values"].values()), float)
        ok = np.isfinite(v).all() and 150 < out["values"]["T@2000"] < 340 and 0 <= out["values"]["RH@3000"] <= 100.01 and 20000 < out["values"]["p@10"] < 110000
        rows.append((name, "OK" if ok else "BAD-VALUES", out["mode"], ";".join(q for q in out["quality"] if q != "nominal")[:60], f"{time.time() - t0:.1f}s"))
    except Exception as e:  # noqa: BLE001
        rows.append((name, "REFUSED", type(e).__name__, str(e)[:90], f"{time.time() - t0:.1f}s"))


for la in np.linspace(31.0, 34.0, 5):
    for lo in np.linspace(-108.0, -101.0, 5):
        case(f"box {la:.2f},{lo:.2f} +1y 15h", la, lo, "2027-07-15T15:00")
for name, (la, lo) in dict(Denver=(39.74, -104.99), Miami=(25.76, -80.19), Seattle=(47.61, -122.33), Toronto=(43.65, -79.38), MexicoCity=(19.43, -99.13), Anchorage=(61.2, -149.9),
                           Dallas=(32.78, -96.8), LasVegas=(36.17, -115.14), Phoenix=(33.45, -112.07)).items():
    case(f"outside: {name}", la, lo, "2027-07-15T15:00")
for when in ("2026-11-06T15:00", "2026-12-25T12:00", "2027-07-15T15:00", "2030-03-01T10:00", "2040-08-10T15:00", "2060-01-15T12:00", "2100-06-21T15:00"):
    case(f"date {when}", 32.9, -106.9, when)
for when in ("1995-07-15T15:00", "2012-03-01T10:00", "2025-06-01T15:00"):
    case(f"past {when} (no ERA5 store)", 32.9, -106.9, when)
for h in range(24):
    case(f"solar hour {h:02d}", 32.9, -106.9, f"2027-07-15T{h:02d}:00")
w = max(len(r[0]) for r in rows)
for r in rows:
    print(f"{r[0]:<{w}}  {r[1]:<10} {r[2]:<18} {r[3]:<92} {r[4]}")
print("\nOK:", sum(r[1] == "OK" for r in rows), " REFUSED (clear message):", sum(r[1] == "REFUSED" for r in rows), " BAD-VALUES:", sum(r[1] == "BAD-VALUES" for r in rows))
