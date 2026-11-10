"""IL-188 (2026-11-10): Denver referee aloft without balloons (IGRA 72469 ends 2022-07): cache the Denver radar (FTG) NEXRAD NVW volumes nearest 23 UTC and 11 UTC (before the 00Z / 12Z
balloon times) for every 3rd day of 2024-25, into data/raw/nexrad_nvw (same cache as P3). Public Unidata Level III bucket, about 9 KB per file. Resumable."""
import os
import sys
from datetime import date, datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from p3_vad_vs_balloon import fetch   # noqa: E402

got = miss = 0
d = date(2024, 1, 1)
while d <= date(2025, 12, 31):
    for hh in (23, 11):
        try:
            p = fetch(datetime(d.year, d.month, d.day), "FTG", hour=hh)
        except Exception as e:  # noqa: BLE001 - network errors: count and continue
            p = None
            print(d, hh, "error", repr(e)[:80], flush=True)
        got, miss = (got + 1, miss) if p else (got, miss + 1)
    d += timedelta(days=3)
print(f"FTG 2024-25: cached {got}, none {miss}", flush=True)
