"""23.T3 step 0: one month (2024-06) of NEXRAD Level III VAD wind profiles at MAF (KMAF 'NVW', Unidata bucket), the first volume of every hour.
Reports: hours with a file, hours with a usable wind profile (>= 3 levels), top height, hour-to-hour coverage. Files -> data/raw/nexrad_nvw_t3 (about 9 KB each). Resumable."""
import os
import sys
import urllib.request
import re
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import p3_vad_vs_balloon as P   # noqa: E402

OUT = os.path.join(REPO, "data", "raw", "nexrad_nvw_t3")
os.makedirs(OUT, exist_ok=True)
SITE = os.environ.get("T3_SITE", "MAF")
ELEV = float(os.environ.get("T3_ELEV", 872.0))                    # KMAF antenna site, m ASL (approx; only shifts heights by a few metres)
days = pd.date_range(os.environ.get("T3_START", "2024-06-01"), os.environ.get("T3_END", "2024-06-30"))
HOURS = range(int(os.environ.get("T3_H0", 0)), 24)   # T3_H0=12 pulls only 12-23 UTC (the hours the coherence kit uses)
rows = []
for d in days:
    for h in HOURS:
        pre = f"{SITE}_NVW_{d:%Y_%m_%d}_{h:02d}"
        try:
            with urllib.request.urlopen(P.BUCKET + f"?list-type=2&prefix={pre}", timeout=60) as r:
                keys = re.findall(r"<Key>([^<]+)</Key>", r.read().decode())
        except Exception as e:  # noqa: BLE001
            keys = []
        n_win = top = 0
        if keys:
            k = keys[0]
            path = os.path.join(OUT, k)
            try:
                if not os.path.exists(path):
                    urllib.request.urlretrieve(P.BUCKET + k, path)
                p = P.parse(path, ELEV)
                if p is not None and np.isfinite(p[0]).sum() >= 3:
                    n_win = 1
                    top = float(P.H[np.isfinite(p[0])].max())
            except Exception:  # noqa: BLE001
                pass
        rows.append((d + pd.Timedelta(hours=h), len(keys), n_win, top))
df = pd.DataFrame(rows, columns=["t", "n_keys", "usable", "top"])
print(f"T3 step 0 MAF 2024-06: hours {len(df)}, hours with a file {int((df.n_keys > 0).sum())}, hours with a usable first volume {int(df.usable.sum())}, median top height {df.top[df.usable == 1].median():.0f} m, files per hour median {df.n_keys.median():.0f}")
runs = (df.usable.values == 0).astype(int)
gaps = np.diff(np.flatnonzero(np.r_[1, np.diff(runs) != 0, 1]))
print("longest run of unusable hours:", int(gaps.max()) if len(gaps) else 0)
if "T3_START" not in os.environ:   # extra pulls do not overwrite the June step-0 csv
    df.to_csv(os.path.join(REPO, "data", "t3_step0.csv"), index=False)
