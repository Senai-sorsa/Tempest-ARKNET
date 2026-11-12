"""New_Plan 13.1 AV2 (variation of N5, KILLED): long-lead-only use. The N5 all-lead network (models/modeF_n5_all{,_den}_s{0,1}) serves only leads
beyond 7.5 d, where the tool today falls back to the climate generator; leads up to 7.5 d untouched. No training, no new run: the N5 test rows
(<stem>_rows.npz: per-row CRPS, lead_days, crps_clim on the same rows) already hold everything. Binned = models/modeF_n5_bin* on the same rows.

Rule (from the plan row, written 2026-11-12 15:10 before this script was run; the parent's pooled beyond-7.5 d numbers and its per-day means
vs climate were already known, its per-day intervals and cov99 were not):
  PASS: at lead day 8, 9 and 10 each (lead_days rounded up, as N5), all-lead better than the binned model AND than climate with the paired
        day-block interval excluding 0, both boxes, both seeds; and at the beyond-7.5 d bin |cov99(all-lead) - cov99(climatology)| <= 0.003
        (climate is what the tool serves there today; cov99 exists only pooled over the bin).
  KILL: all-lead mean CRPS worse than climate at any of day 8 / 9 / 10 in either box (either seed).
  Otherwise MISS (record; standing note of section 13: one more AV row if a benefit has an interval excluding 0).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b8_av2_long_lead.py
Result: docs/results/logs/kit_b8_av2_long_lead.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b5_modeF_alllead import BEYOND, METHOD

DAYS = (8, 9, 10)
CLIM = "climatology (2016-20 pool)"


def cov99(stem, method):
    t = pd.read_csv(stem + "_eval.csv")
    return t[(t.method == method) & (t.lead == BEYOND)].cov99.mean()


def judge(sig, worse_clim, dcov):
    """sig[k][d] = both intervals < 0 at day d; worse_clim[k] = mean worse than climate at some day; dcov[k] = |cov99 diff| -> verdict."""
    if any(worse_clim.values()):
        return "KILL (worse than climate at a day 8-10)"
    ok = all(all(v.values()) for v in sig.values()) and all(c <= 0.003 for c in dcov.values())
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"AV2 N5 all-lead network beyond 7.5 d only; per lead day {DAYS}, per-row CRPS, all-lead minus binned / minus climate (paired day-block 1000)"]
    sig, worse, dcov, missing = {}, {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {k: os.path.join(M, f"modeF_n5_{k}{tag}_s{s}") for k in ("bin", "all")}
            if not all(os.path.exists(v + e) for v in st.values() for e in ("_eval.csv", "_rows.npz")):
                missing.append(f"{box} s{s}")
                continue
            ra, rb = np.load(st["all"] + "_rows.npz"), np.load(st["bin"] + "_rows.npz")
            assert all((ra[f] == rb[f]).all() for f in ("day", "lead", "lead_days")), f"{box} s{s}: arms scored on different rows"
            k = ra["lead"] == BEYOND
            ld = np.ceil(ra["lead_days"][k] - 1e-6).astype(int)
            a, b, c, dy = ra["crps"][k], rb["crps"][k], ra["crps_clim"][k], ra["day"][k]
            sig[(box, s)], worse[(box, s)], parts = {}, False, []
            for d in DAYS:
                m = ld == d
                assert m.sum() > 0, f"{box} s{s}: no rows at day {d}"
                iv = {ref: K.block_boot(a[m] - x[m], list(dy[m]), draws=1000) for ref, x in (("binned", b), ("climate", c))}
                sig[(box, s)][d] = all(hi < 0 for _, _, hi in iv.values())
                worse[(box, s)] |= a[m].mean() > c[m].mean()
                parts.append(f"{d} d (n {m.sum()}): all {a[m].mean():.3f} " + ", ".join(f"{r} {x:+.3f} [{lo:+.3f}, {hi:+.3f}]" for r, (x, lo, hi) in iv.items()))
            ca, cc = cov99(st["all"], METHOD), cov99(st["all"], CLIM)
            dcov[(box, s)] = abs(ca - cc)
            lines.append(f"  {box:<6} seed {s}: " + "; ".join(parts) + f"; cov99 beyond 7.5 d all-lead {ca:.4f} vs climate {cc:.4f} (diff {ca - cc:+.4f})")
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b8_av2_long_lead", lines)
        return
    lines.append("Rule (pre-set): PASS = days 8, 9, 10 each better than binned and climate with interval < 0, both boxes and seeds, cov99 within 0.003 of "
                 "climate; KILL = worse than climate at any day 8-10.")
    lines.append("Verdict: " + judge(sig, worse, dcov))
    K.report("b8_av2_long_lead", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    t = {k: {d: True for d in DAYS} for k in keys}
    no, small = {k: False for k in keys}, {k: 0.001 for k in keys}
    assert judge(t, no, small) == "PASS"
    assert judge(t, {**no, ("B", 1): True}, small).startswith("KILL")
    assert judge({**t, ("A", 0): {8: True, 9: False, 10: True}}, no, small).startswith("MISS")
    assert judge(t, no, {**small, ("A", 1): 0.004}).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
