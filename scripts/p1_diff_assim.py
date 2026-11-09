"""P1: assimilate the DIFFERENCE (station observed minus the tool's own prediction AT the station) instead of the raw station wind. A station's siting bias (an airport's open,
smooth surroundings, its height, its local channelling) is part of its raw value; moved to the pad as it is, it biases the pad. The tool's error at the station should carry over better.
Leave-one-station-out: the "pad" is TCS or MAF (ASOS truth), the source report is from one of its two nearest other ASOS stations at the same hour (age 0). For each random served
hour of 2023 (the obs.py gains were fitted on 2015-2022; 2023 is outside the development window), three updates of the pad's climate pool (mode 'ai', n = 200), all with the same
fitted gain of obs.py (distance, elevation difference, day / night) through Launch.observe:
  none        the pool as it is,
  raw         observe(wind = the station's observed wind)                        (what observe_latest does today),
  difference  observe(wind = pad pool median + (station observed - station pool median)) as a vector (u, v).
Score at the pad: CRPS of u and v (mean) and of the speed, MAE of the speed median, 90 % coverage of the speed.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p1_diff_assim.py [--n 120]
"""
import argparse
import math
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather_v2 import Launch, obs as O   # noqa: E402

PADS = {"TCS": "America/Denver", "MAF": "America/Chicago"}
TZ = {"TCS": "America/Denver", "ONM": "America/Denver", "LRU": "America/Denver", "ELP": "America/Denver", "ALM": "America/Denver", "ABQ": "America/Denver",
      "MAF": "America/Chicago", "FST": "America/Chicago", "PEQ": "America/Chicago"}


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def pool_uv(lat, lon, el, tz, t, seed):
    local = t.astimezone(ZoneInfo(tz)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
    L = Launch(lat, lon, local, tz=tz, mode="ai", n=200, units="si", elevation=el, seed=seed)
    s = L._ensure_pool()["samples"]
    return L, np.asarray(s["u"], float)[:, 0], np.asarray(s["v"], float)[:, 0]


def obs_args(u, v):
    spd = float(math.hypot(u, v))
    frm = float(math.degrees(math.atan2(-u, -v)) % 360.0)
    return spd, frm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    data = {st: gw.load_asos(st, [2023]) for st in O.STATIONS}
    res = {}
    for pad, tzp in PADS.items():
        P = O.STATIONS[pad]
        srcs = sorted((km(P, O.STATIONS[s]), s) for s in O.STATIONS if s != pad and data[s])[:2]
        hours = sorted(data[pad])
        rng.shuffle(hours)
        done = 0
        for t in hours:
            if done >= a.n:
                break
            if not all(t in data[s] for _, s in srcs):
                continue
            try:
                Lp, up, vp = pool_uv(P[0], P[1], P[2], tzp, t, done)
            except Exception:   # noqa: BLE001  (outside the served window)
                continue
            yu, yv = data[pad][t]
            ys = math.hypot(yu, yv)
            local_h = t.astimezone(ZoneInfo(tzp)).hour
            for dist, s in srcs:
                S = O.STATIONS[s]
                try:
                    _, us, vs = pool_uv(S[0], S[1], S[2], TZ[s], t, done + 7)
                except Exception:   # noqa: BLE001
                    continue
                ou, ov = data[s][t]
                cand = {"none": (up, vp)}
                for name, (cu, cv) in (("raw", (ou, ov)), ("difference", (np.median(up) + ou - np.median(us), np.median(vp) + ov - np.median(vs)))):
                    spd, frm = obs_args(cu, cv)
                    try:
                        o = Lp.observe(wind_10m=f"{spd:.3f} m/s", wind_from_deg=frm, age_hours=0.0, distance_km=dist, elevation_diff_m=S[2] - P[2], source=s)
                        so = o._ensure_pool()["samples"]
                        cand[name] = (np.asarray(so["u"], float)[:, 0], np.asarray(so["v"], float)[:, 0])
                    except ValueError:
                        cand[name] = None
                for name, c in cand.items():
                    if c is None:
                        continue
                    cu, cv = c
                    sp = np.hypot(cu, cv)
                    crps_uv = 0.5 * (crps_ensemble(cu[None, :, None], np.array([[yu]]))[0, 0] + crps_ensemble(cv[None, :, None], np.array([[yv]]))[0, 0])
                    crps_s = crps_ensemble(sp[None, :, None], np.array([[ys]]))[0, 0]
                    cov = coverage90(sp[None, :, None], np.array([[ys]]), 0.9)[0, 0]
                    res.setdefault((pad, s, "day" if 8 <= local_h <= 17 else "other", name), []).append((crps_uv, crps_s, abs(np.median(sp) - ys), cov))
            done += 1
        print(f"{pad}: {done} hours of 2023, sources {', '.join(f'{s} ({d:.0f} km)' for d, s in srcs)}", flush=True)
    print("\npad  source part   method       n    CRPS u,v  CRPS speed  MAE speed  cov90 speed")
    for key in sorted(res):
        r = np.array(res[key])
        print(f"{key[0]}  {key[1]}  {key[2]:6s} {key[3]:11s} {len(r):4d}  {r[:, 0].mean():8.3f}  {r[:, 1].mean():9.3f}  {r[:, 2].mean():9.3f}  {r[:, 3].mean():6.2f}")
    print("\nall pads and sources: method CRPS u,v / CRPS speed / MAE speed / cov90 (paired rows)")
    for name in ("none", "raw", "difference"):
        r = np.concatenate([np.array(v) for k, v in res.items() if k[3] == name])
        print(f"  {name:11s} {r[:, 0].mean():.3f} / {r[:, 1].mean():.3f} / {r[:, 2].mean():.3f} / {r[:, 3].mean():.2f}  (n {len(r)})")


if __name__ == "__main__":
    main()
