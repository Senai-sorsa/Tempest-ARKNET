"""Compare two headline CSVs (the baseline and a new model) band by band, and apply the phase pass rule.

    python scripts/compare_headline.py E12_headline.csv NEW_headline.csv [--kind unknown|known] [--md out.md]

Per variable x band: skill15 (CRPS skill vs the 15-year climatology), cov99 (share of truths inside the 99 % range,
target 0.99) and MAE of the median ("most likely value"), each with the day-block interval from the headline file.
A change is flagged only when the two intervals do not overlap.

Pass rule (PHASED_PLAN 0.3), all three must hold:
  (a) mean skill15 is not lower than the baseline's;
  (b) no variable x band is worse with non-overlapping intervals (skill15 lower, or cov99 farther from 0.99);
  (c) mean |cov99 - 0.99| is not worse by more than 0.001.
Optional (both off by default, so old verdicts are unchanged):
  --tol T            rule (a) becomes mean skill15 >= baseline - T (IL-109: T from the 3-seed spread, not a guess);
  --require-gauss    rule (d): when the CSV has margin_gauss_<kind> (IL-111), the mean margin over the Gaussian
                     (Earth-GRAM style) baseline must be > 0 and no band's margin interval may lie below 0.
                     Without the flag the margin is only printed.
Exit code 0 = pass, 1 = fail.
"""
import argparse
import sys

import pandas as pd


def compare(base, new, kind="unknown", tol=0.0, require_gauss=False):
    key = ["var", "band"]
    b, n = base.set_index(key), new.set_index(key)
    common = b.index.intersection(n.index)
    s, c = f"skill15_{kind}", f"cov99_{kind}"
    rows = []
    for k in common:
        x, y = b.loc[k], n.loc[k]
        sk_worse = y[s + "_hi"] < x[s + "_lo"]
        sk_better = y[s + "_lo"] > x[s + "_hi"]
        disjoint = y[c + "_hi"] < x[c + "_lo"] or y[c + "_lo"] > x[c + "_hi"]
        cov_worse = disjoint and abs(y[c] - 0.99) > abs(x[c] - 0.99)
        cov_better = disjoint and abs(y[c] - 0.99) < abs(x[c] - 0.99)
        rows.append(dict(var=k[0], band=k[1], skill15_base=x[s], skill15_new=y[s], d_skill15=y[s] - x[s],
                         skill_flag="WORSE" if sk_worse else "better" if sk_better else "",
                         cov99_base=x[c], cov99_new=y[c], cov_flag="WORSE" if cov_worse else "better" if cov_better else "",
                         mae_base=x.get(f"mae_{kind}"), mae_new=y.get(f"mae_{kind}")))
    t = pd.DataFrame(rows)
    a = t.skill15_new.mean() >= t.skill15_base.mean() - tol
    bb = not ((t.skill_flag == "WORSE") | (t.cov_flag == "WORSE")).any()
    dev_b, dev_n = (t.cov99_base - 0.99).abs().mean(), (t.cov99_new - 0.99).abs().mean()
    cc = dev_n - dev_b <= 0.001
    summary = dict(mean_skill15_base=t.skill15_base.mean(), mean_skill15_new=t.skill15_new.mean(),
                   mean_abs_cov_dev_base=dev_b, mean_abs_cov_dev_new=dev_n, pass_a=bool(a), pass_b=bool(bb),
                   pass_c=bool(cc), passed=bool(a and bb and cc), cells=len(t),
                   min_cov99_new=t.cov99_new.min())
    g = f"margin_gauss_{kind}"
    if g in new.columns:
        nm = new.set_index(key).loc[common]
        summary["gauss_margin_mean"] = float(nm[g].mean())
        summary["gauss_bands_lost"] = int((nm[g + "_hi"] < 0).sum())
        summary["pass_d"] = bool(summary["gauss_margin_mean"] > 0 and summary["gauss_bands_lost"] == 0)
        if require_gauss:
            summary["passed"] = bool(summary["passed"] and summary["pass_d"])
    elif require_gauss:
        summary["pass_d"] = False
        summary["passed"] = False
    return t, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--kind", default="unknown", choices=["unknown", "known"])
    ap.add_argument("--tol", type=float, default=0.0, help="allowed drop in mean skill15 for rule (a)")
    ap.add_argument("--require-gauss", action="store_true", help="make the Gaussian-baseline margin (rule d) gating")
    ap.add_argument("--md", help="also write the table as markdown")
    a = ap.parse_args()
    t, s = compare(pd.read_csv(a.base), pd.read_csv(a.new), a.kind, a.tol, a.require_gauss)
    with pd.option_context("display.width", 200, "display.max_rows", 500, "display.float_format", "{:.4f}".format):
        print(t.to_string(index=False))
    print()
    print(f"mean skill15      base {s['mean_skill15_base']:+.4f}  new {s['mean_skill15_new']:+.4f}   rule (a) {'PASS' if s['pass_a'] else 'FAIL'}")
    print(f"no band worse     rule (b) {'PASS' if s['pass_b'] else 'FAIL'}")
    print(f"mean |cov99-0.99| base {s['mean_abs_cov_dev_base']:.4f}  new {s['mean_abs_cov_dev_new']:.4f}   rule (c) {'PASS' if s['pass_c'] else 'FAIL'}"
          f"   (lowest cov99 in any band {s['min_cov99_new']:.4f}, goal >= 0.98)")
    if "pass_d" in s and ("gauss_margin_mean" in s or a.require_gauss):
        print(f"margin over Gaussian baseline: mean {s.get('gauss_margin_mean', float('nan')):+.4f}, bands clearly below 0: "
              f"{s.get('gauss_bands_lost', 'n/a')}   rule (d) {'PASS' if s['pass_d'] else 'FAIL'}"
              f"{'' if a.require_gauss else ' (informational)'}")
    print("PHASE RESULT:", "PASS" if s["passed"] else "FAIL")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(t.round(4).to_markdown(index=False) if hasattr(t, "to_markdown") else t.round(4).to_string(index=False))
    sys.exit(0 if s["passed"] else 1)


if __name__ == "__main__":
    main()
