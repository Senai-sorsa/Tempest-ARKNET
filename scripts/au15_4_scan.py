"""15.4 helper (New_Plan 15.4): list every interval "[lo, hi]" in the verdict records that excludes 0 with its nearer edge within
one interval width of 0 (the plan's AU-4 criterion: such a verdict needs its interval recomputed with day blocks or the
mark "interval to confirm"). Intervals that include 0, or clear 0 by more than their width, are counted only.
Usage: python scripts/au15_4_scan.py [files...]  (default: New_Plan.md section 9, docs/logs/LOOP3.md, docs/logs/AUTOPILOT.md)"""
import re
import sys

NUM = r"[+-]?\d*\.?\d+"
PAIR = re.compile(rf"\[\s*({NUM})\s*(%?)\s*,\s*({NUM})\s*%?\s*\]")


def near_zero(lo, hi):
    """True when [lo, hi] excludes 0 and its nearer edge lies within one width of 0."""
    if lo > hi or lo <= 0 <= hi:
        return False
    return min(abs(lo), abs(hi)) < hi - lo


assert near_zero(-0.140, -0.009) and near_zero(-0.116, -0.042) and not near_zero(-0.2, -0.15) and not near_zero(-0.1, 0.2) and not near_zero(1.14, 1.53)


def scan(path, lines=None):
    text = open(path, encoding="utf-8").read().splitlines()
    lo_l, hi_l = lines or (1, len(text))
    out, n = [], 0
    for i in range(lo_l - 1, min(hi_l, len(text))):
        line = text[i]
        for m in PAIR.finditer(line):
            lo, hi = float(m.group(1)), float(m.group(3))
            n += 1
            if near_zero(lo, hi):
                head = line.split("|")[1].strip()[:70] if line.startswith("|") else line[:70]
                out.append((i + 1, head, m.group(0), line[max(0, m.start() - 70):m.start()].replace("\n", " ")))
    return n, out


if __name__ == "__main__":
    targets = [(a, None) for a in sys.argv[1:]] or [("New_Plan.md", (206, 293)), ("docs/logs/LOOP3.md", None), ("docs/logs/AUTOPILOT.md", None)]
    for path, rng in targets:
        n, hits = scan(path, rng)
        print(f"== {path}: {n} intervals, {len(hits)} exclude 0 within one width")
        for ln, head, iv, ctx in hits:
            print(f"{path}:{ln} | {head} | ...{ctx} {iv}")
