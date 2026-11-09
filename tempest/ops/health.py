"""Health report for the forecast archive and the tool assets (operations.md O2-O8, scaled to what exists).

    python -m tempest.ops.health [--root data/ops] [--assets tempest_weather/assets] [--json out.json]

Checks, per site and source: files stored, newest file and its age, missing 12-hour slots in the last 14 days (ensembles) or missing days (EC46); last
good / rejected requests from logger.log; asset hashes against the manifest. Exit code 1 if anything is stale (older than 36 h for the ensembles, 60 h for
EC46), has a gap in the last 3 days, or an asset hash differs. Freshness rule used by the tool: <= 12 h nominal, 12-36 h stale, > 36 h do not use.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone


def slots_expected(now, days, step_h):
    t = now.replace(minute=0, second=0, microsecond=0)
    t = t.replace(hour=t.hour // step_h * step_h) if step_h < 24 else t.replace(hour=0)
    return [t - timedelta(hours=step_h * k) for k in range(int(days * 24 / step_h))]


def scan(root, now):
    out = {}
    raw = os.path.join(root, "raw")
    if not os.path.isdir(raw):
        return out
    for site in sorted(os.listdir(raw)):
        for source in sorted(os.listdir(os.path.join(raw, site))):
            d = os.path.join(raw, site, source)
            names = sorted(f[:-8] for f in os.listdir(d) if f.endswith(".json.gz"))
            daily = source == "ecmwf_ec46"
            def parse(nm):
                return datetime.strptime(nm, "%Y%m%d").replace(tzinfo=timezone.utc) if daily else datetime.strptime(nm, "%Y%m%d_%Hz").replace(tzinfo=timezone.utc)
            stamps = [parse(n) for n in names]
            newest = max(stamps) if stamps else None
            have = set(stamps)
            step = 24 if daily else 12
            first = min(stamps) if stamps else now
            expected = [s for s in slots_expected(now, 14, step) if s >= first]
            missing = sorted(s for s in expected if s not in have and s <= now - timedelta(hours=6))
            age_h = (now - newest).total_seconds() / 3600 if newest else None
            limit = 60 if daily else 36
            out[f"{site}/{source}"] = dict(files=len(names), newest=str(newest), age_hours=None if age_h is None else round(age_h, 1),
                                           missing_slots_14d=[str(m) for m in missing], recent_gap=any(m > now - timedelta(days=3) for m in missing),
                                           stale=age_h is None or age_h > limit)
    return out


def log_summary(root, now):
    path = os.path.join(root, "logger.log")
    if not os.path.exists(path):
        return {}
    rej, ok, last_rej = 0, 0, None
    cut = now - timedelta(days=3)
    for ln in open(path, encoding="utf-8"):
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)Z (.*)", ln)
        if not m or datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) < cut:
            continue
        if "REJECTED" in m.group(2):
            rej, last_rej = rej + 1, ln.strip()
        elif ": stored" in m.group(2):
            ok += 1
    return dict(stored_last_3d=ok, rejected_last_3d=rej, last_rejected=last_rej)


def assets_check(path):
    mf = os.path.join(path, "manifest.json")
    if not os.path.exists(mf):
        return dict(present=False)
    man = json.load(open(mf, encoding="utf-8"))
    bad = []
    for name, want in man["files"].items():
        p = os.path.join(path, name)
        if not os.path.exists(p):
            bad.append(f"{name}: missing")
            continue
        with open(p, "rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != want:
                bad.append(f"{name}: hash differs")
    return dict(present=True, created=man.get("created"), model=man.get("model_source"), problems=bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="data/ops")
    ap.add_argument("--assets", default="tempest_weather/assets")
    ap.add_argument("--json")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    rep = dict(time=str(now), sources=scan(a.root, now), logger=log_summary(a.root, now), assets=assets_check(a.assets))
    problems = [k for k, v in rep["sources"].items() if v["stale"] or v["recent_gap"]] + rep["assets"].get("problems", [])
    rep["ok"] = not problems
    for k, v in rep["sources"].items():
        print(f"{k:<48} files {v['files']:>3}  newest {v['newest'][:16]}  age {v['age_hours']} h  missing(14d) {len(v['missing_slots_14d'])}  {'STALE' if v['stale'] else ''}{' GAP' if v['recent_gap'] else ''}")
    print("logger last 3 days:", rep["logger"])
    print("assets:", rep["assets"])
    print("HEALTH:", "OK" if rep["ok"] else f"PROBLEMS: {problems}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    raise SystemExit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
