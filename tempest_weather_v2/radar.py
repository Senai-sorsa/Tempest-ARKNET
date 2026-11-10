"""P3: NEXRAD VAD wind profiles (Level III "NVW", the radar's own wind estimate every few minutes up to about 10 km) as a launch-day upper-air observation.

    prof = latest_profile("EPZ", "2026-07-04T18:00:00Z")      # -> dict(site, time, heights_asl_m, u, v)  (u east, v north, m/s)
    Launch(...).observe_radar()                                # nearest radar, latest volume, conditions the atmosphere

Evidence (scripts/p3_vad_condition.py, El Paso radar vs the EPZ balloons, 120 days 2021-23, 00Z): conditioning the climate pool on the radar wind at 500 / 1000 / 1500 / 2000 m with a sensor sd
of 3 m/s improves the wind above (never observed) by CRPS +32 % at 2.5-5 km, +16 % at 5-12 km, +7 % at 12-18 km, 90 % coverage 0.93-0.94. Using every radar level to 5 km with the same sd
over-tightens (coverage 0.49 where it overlaps), so four levels is the default. Tested only at a radar next to the balloon site; a radar 100 km from the pad (Holloman for Spaceport America)
sees other air: its value should get a larger error (not yet measured, flagged).
Data: the public Unidata Level III archive on AWS (unidata-nexrad-level3, about 9 KB per file, no key). Needs MetPy for the decoding (`metpy.io.Level3File`); without it a clear error.
"""
import math
import re
import urllib.request
from datetime import datetime, timedelta, timezone

BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
# WSR-88D sites near the served boxes: id -> (lat, lon, ground elevation m). APPROXIMATE positions; the NWS radar list is the authority.
RADARS = {"EPZ": (31.873, -106.698, 1252.0), "HDX": (33.077, -106.120, 1287.0), "MAF": (31.943, -102.189, 874.0), "FDX": (34.634, -103.619, 1417.0), "ABX": (35.150, -106.824, 1789.0),
          "FTG": (39.787, -104.546, 1675.0), "PUX": (38.459, -104.181, 1600.0)}
VAD_SIGMA_MS = 3.0                                     # radar-minus-balloon vector wind error at 0.5-2 km (scripts/p3_vad_vs_balloon.py): 2.9-3.2 m/s


def nearest(lat, lon):
    """-> (site id, distance km) of the nearest radar in RADARS."""
    def km(a, b):
        la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 6371.0 * 2 * math.asin(math.sqrt(h))
    return min(((s, km((lat, lon), v)) for s, v in RADARS.items()), key=lambda x: x[1])


def _list(prefix, fetch):
    body = fetch(BUCKET + f"?list-type=2&prefix={prefix}")
    return re.findall(r"<Key>([^<]+)</Key>", body.decode() if isinstance(body, bytes) else body)


def _get(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def parse_nvw(data):
    """Bytes (or a path) of one NVW file -> (heights above sea level m, u, v) from its 'VAD Algorithm Output' tab pages (altitude in hundreds of feet)."""
    try:
        from metpy.io import Level3File
    except ImportError as e:
        raise ImportError("radar profiles need MetPy (pip / uv install metpy) to decode the NEXRAD Level III files") from e
    import io
    f = Level3File(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
    alt, u, v = [], [], []
    for page in f.tab_pages or []:
        for line in page.splitlines():
            p = line.split()
            if len(p) >= 3 and re.fullmatch(r"\d{3}", p[0]):
                try:
                    alt.append(float(p[0]) * 30.48)
                    u.append(float(p[1]))
                    v.append(float(p[2]))
                except ValueError:
                    continue
    order = sorted(range(len(alt)), key=lambda i: alt[i])
    return [alt[i] for i in order], [u[i] for i in order], [v[i] for i in order]


def latest_profile(site, when_utc, max_age_min=45, fetch=None):
    """The newest NVW volume of `site` at or before `when_utc` (ISO string or aware datetime), at most max_age_min old. -> dict(site, time, heights_asl_m, u, v), or None if none."""
    fetch = fetch or _get
    t = datetime.fromisoformat(str(when_utc).replace("Z", "+00:00")) if not isinstance(when_utc, datetime) else when_utc
    t = t.astimezone(timezone.utc)
    best = None
    for hh in (t, t - timedelta(hours=1)):
        for k in _list(f"{site}_NVW_{hh:%Y_%m_%d_%H}", fetch):
            m = re.search(r"_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})$", k)
            if not m:
                continue
            tk = datetime(*map(int, m.groups()), tzinfo=timezone.utc)
            if tk <= t and (t - tk) <= timedelta(minutes=max_age_min) and (best is None or tk > best[0]):
                best = (tk, k)
        if best:
            break
    if best is None:
        return None
    z, u, v = parse_nvw(fetch(BUCKET + best[1]))
    if len(z) < 3:
        return None
    return dict(site=site, time=best[0].isoformat(), heights_asl_m=z, u=u, v=v)
