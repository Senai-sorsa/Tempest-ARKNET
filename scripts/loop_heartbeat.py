"""Heartbeat shared by the two wake-up loops (docs/plans/FIVE_DAY_PLAN.md).

    python scripts/loop_heartbeat.py --kind primary --item 1.2 --note "C1 stage 1"     write a heartbeat (start of every tick)
    python scripts/loop_heartbeat.py --check [--max-min 55]                             print ALIVE or PRIMARY_DEAD and the age (backup tick)
Files: data/loop_heartbeat.json (latest), data/loop_ticks.log (one line per tick). stdlib only.
"""
import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HB = os.path.join(ROOT, "data", "loop_heartbeat.json")
LOG = os.path.join(ROOT, "data", "loop_ticks.log")


def read():
    try:
        with open(HB, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["primary", "backup", "manual"], default="manual")
    ap.add_argument("--item", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--max-min", type=float, default=55.0)
    a = ap.parse_args()
    now = datetime.now()
    if a.check:
        hb = read()
        if not hb:
            print("PRIMARY_DEAD (no heartbeat file)")
            return 1
        age = (now - datetime.fromisoformat(hb["time"])).total_seconds() / 60.0
        # the newest heartbeat of ANY kind counts: it proves some loop is alive; the primary is dead when the newest PRIMARY heartbeat is old
        prim = datetime.fromisoformat(hb.get("last_primary", hb["time"]))
        page = (now - prim).total_seconds() / 60.0
        print(f"{'ALIVE' if page <= a.max_min else 'PRIMARY_DEAD'}: newest heartbeat {age:.0f} min ago ({hb['kind']}, item {hb.get('item')}), newest primary {page:.0f} min ago")
        return 0 if page <= a.max_min else 1
    prev = read() or {}
    hb = dict(time=now.isoformat(timespec="seconds"), kind=a.kind, item=a.item, note=a.note, tick=int(prev.get("tick", 0)) + 1,
              last_primary=now.isoformat(timespec="seconds") if a.kind == "primary" else prev.get("last_primary", now.isoformat(timespec="seconds")))
    os.makedirs(os.path.dirname(HB), exist_ok=True)
    tmp = HB + f".tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hb, f)
    os.replace(tmp, HB)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{hb['time']} tick {hb['tick']} {a.kind} item {a.item} {a.note}\n")
    print(f"heartbeat {hb['tick']} written ({a.kind}, item {a.item})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
