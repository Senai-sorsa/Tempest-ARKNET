"""A24 (2026-11-10): cache the NEXRAD NVW volumes nearest 11:30 UTC (before the 12Z balloon, about 05 h solar) for EPZ on the days 2021-23 that have a 12Z EPZ sounding, for the night version of
the P3 radar test (scripts/p3_vad_condition.py is 00Z only so far). Public Unidata Level III bucket, about 9 KB per file, into data/raw/nexrad_nvw (same cache as P3). Resumable."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from p3_vad_vs_balloon import fetch   # noqa: E402
from tempest.calibrate import station   # noqa: E402

t, _, _ = station.read_igra(os.path.join(REPO, "data/raw/igra/USM00072364-drvd.txt.zip"), 2021, 2023)
days = sorted({x.normalize() for x in t[(t.year >= 2021) & (t.year <= 2023) & (t.hour == 12)]})
got = miss = 0
for d in days[::3]:
    try:
        p = fetch(d.to_pydatetime(), "EPZ", hour=11)
    except Exception as e:  # noqa: BLE001 - network errors: skip the day, report the count
        p = None
        print(d.date(), "error", repr(e)[:80], flush=True)
    got, miss = (got + 1, miss) if p else (got, miss + 1)
print(f"12Z days {len(days)}, tried {len(days[::3])}, cached {got}, none {miss}", flush=True)
