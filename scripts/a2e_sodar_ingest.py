"""Copy WFIP1 sodar CSVs from Downloads into data/raw/a2e/wfip1_sodar_<site>/,
write a cleaned file (-999 -> blank, ISO timestamps, same 10-min rows) and a per-level coverage CSV.
Raw files are copied, never modified or deleted. Timezone is NOT asserted (timestamps kept as given)."""
import csv, shutil, sys
from datetime import datetime
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads"
DST = Path(__file__).resolve().parents[1] / "data" / "raw" / "a2e"
SITES = {"z02": "brady", "z03": "cleburne", "z04": "colorado_city", "z05": "jayton", "z09": "ozona"}
FMTS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M")  # z02 has seconds, others do not

def iso(s):
    for f in FMTS:
        try: return datetime.strptime(s.strip(), f).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError: pass
    raise ValueError(f"unparsed timestamp {s!r}")

def process(src, site):
    out = DST / f"wfip1_sodar_{site}"; out.mkdir(parents=True, exist_ok=True)
    raw = out / src.name
    if not raw.exists(): shutil.copy2(src, raw)
    with open(src, newline="") as f:
        r = csv.reader(f); hdr = next(r); rows = list(r)
    n, ok, bad = len(rows), [0] * len(hdr), 0
    clean = out / (src.stem + ".clean.csv")
    with open(clean, "w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr)
        for x in rows:
            if len(x) != len(hdr): bad += 1; continue
            x = list(x); x[0], x[1] = iso(x[0]), iso(x[1])
            for i in range(2, len(x)):
                if x[i].strip() in ("-999", "-999.0", ""): x[i] = ""
                else: ok[i] += 1
            w.writerow(x)
    n -= bad
    with open(out / (src.stem + ".coverage.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["column", "valid", "total", "pct"])
        for i in range(2, len(hdr)): w.writerow([hdr[i], ok[i], n, f"{100*ok[i]/max(n,1):.1f}"])
    print(f"{site:14s} {src.name}: {n} rows ({bad} malformed dropped) -> {out}")

for z, site in SITES.items():
    for p in sorted(SRC.glob(f"sodar.{z}.*.csv")):
        if not p.name.endswith(".clean.csv"): process(p, site)
