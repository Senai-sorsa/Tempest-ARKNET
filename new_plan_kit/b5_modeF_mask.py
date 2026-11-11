"""New_Plan 10.4 N4: optional sources in one network. Verdict on the runs of scripts/cpu_n4_mask.sh (ENSF2 recipe + --ens-mask 0.3, each network
scored with the feed and, via --ens-absent, without it) against the existing single-purpose networks on the same rows and seeds:
    with feed    models/modeF_ensmask{,_den}_s{0,1}_eval.csv        vs ENSF2       models/modeF_ens{,_den}{,_s1}_eval.csv
    without      models/modeF_ensmask{,_den}_s{0,1}_noens_eval.csv  vs HRES-only   models/modeF_ensbase{,_den}{,_s1}_eval.csv
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, method 'network + PIT recal + range map + Schaake shuffle' (as the ENSF2 verdict).
PASS (pre-set): at every lead, with feed <= ENSF2 x 1.005 and without <= HRES-only x 1.005, both boxes, both seeds.
KILL: either side worse by more than 1 % (mean over leads) in both seeds (any box). Otherwise: one extra arm at width 192.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_mask.py
Result: docs/results/logs/kit_b5_modeF_mask.log
"""
import os

import pandas as pd

import kit_common as K

METHOD = "network + PIT recal + range map + Schaake shuffle"
LEADS = (1, 3, 5, 7)


def by_lead(path):
    t = pd.read_csv(path)
    return t[t.method == METHOD].groupby("lead").crps.mean().reindex(LEADS)


def judge(rel):
    """rel[(box, seed, side)] = per-lead ratio mask / reference -> (verdict, pass flag, kill flag)."""
    ok = all((r <= 1.005).all() for r in rel.values())
    kill = any(all(rel[(b, s, side)].mean() > 1.01 for s in (0, 1)) for b in {k[0] for k in rel} for side in ("feed", "no feed"))
    return ("PASS" if ok else "KILL" if kill else "MISS -> width 192 arm"), ok, kill


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N4 one network with optional ensemble inputs (30 % masked + present bit); mean CRPS by lead {LEADS}, {METHOD}"]
    rel, missing = {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            sfx = "" if s == 0 else f"_s{s}"
            pairs = {"feed": (f"modeF_ensmask{tag}_s{s}_eval.csv", f"modeF_ens{tag}{sfx}_eval.csv"),
                     "no feed": (f"modeF_ensmask{tag}_s{s}_noens_eval.csv", f"modeF_ensbase{tag}{sfx}_eval.csv")}
            for side, (fm, fr) in pairs.items():
                if not all(os.path.exists(os.path.join(M, f)) for f in (fm, fr)):
                    missing.append(f"{box} s{s} {side}")
                    continue
                m, r = by_lead(os.path.join(M, fm)), by_lead(os.path.join(M, fr))
                rel[(box, s, side)] = m / r
                lines.append(f"  {box:<6} seed {s} {side:<7}: mask " + " / ".join(f"{v:.3f}" for v in m) + "  ref " + " / ".join(f"{v:.3f}" for v in r)
                             + "  change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in m / r) + " %")
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b5_modeF_mask", lines)
        return
    lines.append("Rule (pre-set): every lead within +0.5 % of the reference on both sides, both boxes, both seeds; KILL if a side is > +1 % (mean of leads) in both seeds.")
    lines.append("Verdict: " + judge(rel)[0])
    K.report("b5_modeF_mask", lines)


def _selfcheck():
    one = pd.Series([1.0] * 4, index=LEADS)
    keys = [(b, s, side) for b in ("A", "B") for s in (0, 1) for side in ("feed", "no feed")]
    assert judge({k: one * 1.004 for k in keys})[0] == "PASS"
    assert judge({k: one * (1.02 if k[2] == "no feed" else 1.0) for k in keys})[0] == "KILL"
    assert judge({k: one * (1.008 if k[1] == 0 else 1.0) for k in keys})[0].startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
