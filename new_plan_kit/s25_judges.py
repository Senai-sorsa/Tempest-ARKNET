"""New_Plan section 25 judges, one function per item, each with its PRE-SET RULE in its docstring (written before any run).

    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py ITEM      ITEM: gf2 gf2_follow gf4 gf1_screen gf1
                                                                                                      gx2 gt2 gf3 mf2 gx1 gt1 mf1 h1 h3 h4 h2 h5 n1c4w av34s25 av19s25 x4s25 x4bs25 x4cs25
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py --selfcheck
Result: docs/results/logs/kit_s25_<item>.log (a VERDICT line); picks for a phase-2 run go to docs/results/logs/s25_<item>_pick.txt.

25.1 rules shared by every paired judge (paired_rule below):
  inputs are scripts/s25_arm.sh outputs in models/s25/: NAME_sSEED_cal2021_headline.csv (a), ..._cal2021_smap_shufc8_lmap_headline.csv (b),
  NAME_sSEED_diag_{a,b_cell8}.csv (scripts/diagnose.py), NAME_sSEED_s25shape_{a,b_cell8}.csv (scripts/s25_shape.py); seeds 0 and 100;
  the paired baseline is "base" (6000 steps) or "base3k" (3000-step screens), trained on the same data and seeds.
  PASS needs, in BOTH seeds, on stack (b): mean skill15 (unknown drivers) >= base - 0.0009; compare_shape not WORSE on any metric (noise = the
  other base seed); preclip_rate (RH) not worse by > 0.0005; cov99 not worse (compare_headline pass_c and no band flagged WORSE);
  and the item's target better than the base by more than seed noise.
  Seed noise of a metric = |base_s0 - base_s100| on that metric (assumption, New_Plan 25.1 does not define it; recorded in SECTION25_CODE_STATUS).
  KILL: the target inside seed noise in either seed, or a shape FAIL in either seed. Anything else (target wins, a skill / preclip / cov99 gate
  fails): MISS. Denver fill-top skill15 is printed every time (report, not a gate).
"""
import os
import sys

import numpy as np
import pandas as pd

import kit_common as K
import compare_headline as CH
import compare_shape as CS

D = os.path.join(K.REPO, "models", "s25")
SEEDS = (0, 100)
TOL = K.PAIRED_TOL                     # 0.0009 skill15
PRECLIP_TOL = 0.0005


# ---------------------------------------------------------------- file access
def f_head(name, s, stack, tag="cell8"):
    st = "" if stack == "a" else ("_smap_shufc8_lmap" if tag == "cell8" else "_smap_lmap")
    return os.path.join(D, f"{name}_s{s}_cal2021{st}_headline.csv")


def f_diag(name, s, stack, tag="cell8"):
    return os.path.join(D, f"{name}_s{s}_diag_" + ("a" if stack == "a" else f"b_{tag}") + ".csv")


def f_shape(name, s, stack, tag="cell8"):
    return os.path.join(D, f"{name}_s{s}_s25shape_" + ("a" if stack == "a" else f"b_{tag}") + ".csv")


def need(*paths):
    miss = [p for p in paths if not os.path.exists(p)]
    if miss:
        raise SystemExit("missing inputs (run the item's runner first): " + ", ".join(os.path.relpath(p, K.REPO) for p in miss))


def skill15(name, s, stack="b", tag="cell8"):
    return float(pd.read_csv(f_head(name, s, stack, tag)).skill15_unknown.mean())


def shape_val(name, s, stack, metric, band=None, var=None, tag="cell8", src="shape"):
    t = pd.read_csv(f_shape(name, s, stack, tag) if src == "shape" else f_diag(name, s, stack, tag))
    t = t[t.metric == metric]
    if band is not None:
        t = t[t.band == band]
    if var is not None:
        t = t[t["var"].isin([var] if isinstance(var, str) else var)]
    return float(t.value.abs().mean())


def denver(name, s):
    p = os.path.join(D, f"{name}_s{s}_den_cal2021_headline.csv")
    return f"{pd.read_csv(p).skill15_unknown.mean():+.4f}" if os.path.exists(p) else "n/a"


# ---------------------------------------------------------------- targets (lower is better; composites normalised by base seed 0)
def t_vcorr_vario(name, s, stack="b", tag="cell8"):
    """GF1 / GX1 / H3 target: vcorr error by separation band + variogram score."""
    return shape_val(name, s, stack, "vcorr_sep", tag=tag), shape_val(name, s, stack, "variogram", tag=tag)


def t_gf3(name, s, stack="b", tag="cell8"):
    """GF3 / MF2 / MF1 target: vcorr (diagnose) and |Ri<1 share - truth| at 12-18 km, on the given stack."""
    ri = abs(shape_val(name, s, stack, "ri_lt1_share", "12-18 km", tag=tag) - shape_val(name, s, stack, "ri_lt1_truth", "12-18 km", tag=tag))
    return shape_val(name, s, stack, "vcorr_err", tag=tag, src="diag"), ri


def t_gf3_ab(name, s, stack="b", tag="cell8"):
    return t_gf3(name, s, "a", tag) + t_gf3(name, s, "b", tag)


def t_gt1(name, s, stack="b", tag="cell8"):
    """GT1 target: vcorr error across neighbouring height blocks + mean |shear p99 ratio - 1|."""
    p99 = pd.read_csv(f_shape(name, s, stack, tag)).query("metric == 'shear_p99_ratio'").value
    return shape_val(name, s, stack, "vcorr_nbr", tag=tag), float((p99 - 1).abs().mean())


def composite(fn, name, s, base, stack="b", tag="cell8"):
    ref = np.maximum(np.asarray(fn(base, 0, stack), float), 1e-9)
    return float((np.asarray(fn(name, s, stack, tag), float) / ref).mean())


# ---------------------------------------------------------------- the shared 25.1 rule
def gates(name, s, base, tag="cell8"):
    """-> dict of the 25.1 non-target gates on stack (b) for one seed, plus the numbers behind them."""
    other = SEEDS[1] if s == SEEDS[0] else SEEDS[0]
    need(f_head(base, s, "b"), f_head(name, s, "b", tag), f_diag(base, s, "b"), f_diag(name, s, "b", tag), f_diag(base, other, "b"))
    t, sm = CH.compare(pd.read_csv(f_head(base, s, "b")), pd.read_csv(f_head(name, s, "b", tag)), "unknown")
    sh = CS.compare(f_diag(base, s, "b"), f_diag(name, s, "b", tag), noise=[f_diag(base, other, "b")])
    pre = shape_val(name, s, "b", "preclip_rate", tag=tag, src="diag") - shape_val(base, s, "b", "preclip_rate", src="diag")
    d = sm["mean_skill15_new"] - sm["mean_skill15_base"]
    return dict(d_skill15=d, skill_ok=d >= -TOL, shape_fail=bool((sh.flag == "WORSE").any()), shape_worse=",".join(sh.metric[sh.flag == "WORSE"]),
                preclip=pre, preclip_ok=pre <= PRECLIP_TOL, cov_ok=bool(sm["pass_c"] and not (t.cov_flag == "WORSE").any()))


def target_wins(fn, name, base, tag="cell8", stack="b"):
    """-> per seed (arm value, base value, noise, beats) with noise = |base_s0 - base_s100| of the composite target."""
    tb = {s: composite(fn, base, s, base, stack) for s in SEEDS}
    noise = abs(tb[SEEDS[0]] - tb[SEEDS[1]])
    out = {}
    for s in SEEDS:
        ta = composite(fn, name, s, base, stack, tag)
        out[s] = (ta, tb[s], noise, tb[s] - ta > noise)
    return out


def paired_rule(name, base, fn, L, tag="cell8", stack="b"):
    """Apply the 25.1 rule to arm `name` vs `base` with target fn; append report lines; return PASS / KILL / MISS."""
    wins = target_wins(fn, name, base, tag, stack)
    gs = {s: gates(name, s, base, tag) for s in SEEDS}
    for s in SEEDS:
        ta, tb, nz, ok = wins[s]
        g = gs[s]
        L.append(f"  {name} s{s}: target {ta:.4f} vs base {tb:.4f} (noise {nz:.4f}) {'beats' if ok else 'inside noise'}; d_skill15(b) {g['d_skill15']:+.4f}"
                 f" {'ok' if g['skill_ok'] else 'FAIL'}; shape {'FAIL ' + g['shape_worse'] if g['shape_fail'] else 'ok'}; preclip {g['preclip']:+.5f}"
                 f" {'ok' if g['preclip_ok'] else 'FAIL'}; cov99 {'ok' if g['cov_ok'] else 'FAIL'}; Denver skill15 {denver(name, s)} (report)")
    if any(g["shape_fail"] for g in gs.values()) or not all(w[3] for w in wins.values()):
        return "KILL"
    if all(g["skill_ok"] and g["preclip_ok"] and g["cov_ok"] for g in gs.values()):
        return "PASS"
    return "MISS"


def pick(item, names):
    with open(os.path.join(K.LOGS, f"s25_{item}_pick.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(names) + "\n")


def read_pick(item):
    p = os.path.join(K.LOGS, f"s25_{item}_pick.txt")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return [x.strip() for x in fh if x.strip()]


# ---------------------------------------------------------------- GF2
GF2_LR, GF2_WD = ("3e-4", "1e-3", "3e-3"), ("1e-5", "1e-4", "1e-3")
GF2_CENTRE = "gf2_l1e-3_w1e-4"            # the shipped settings (c4w lr 1e-3, wd 1e-4) at 3000 steps


def val_crps(path):
    """Validation CRPS at the stop step = the best (restored) validation loss, mean over members."""
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=True)
    return float(np.mean([min(h[2] for h in mb["history"]) for mb in ck["members"]]))


def gf2(L):
    """GF2 PRE-SET RULE: 3 x 3 grid lr {3e-4, 1e-3, 3e-3} x wd {1e-5, 1e-4, 1e-3}, 3000 steps, seed 0, train only. Target: validation CRPS
    (2021-23) at the stop step. Seed noise = |centre s0 - centre s100| (centre = shipped lr 1e-3, wd 1e-4).
    KILL: no cell beats the shipped settings by more than seed noise. Otherwise PASS and the best cell is written to s25_gf2_pick.txt for the
    follow-up (best cell, batch 16384, lr x 2, 12000 steps)."""
    cells = {f"gf2_l{a}_w{b}": os.path.join(D, f"gf2_l{a}_w{b}_s0.pt") for a in GF2_LR for b in GF2_WD}
    cen1 = os.path.join(D, f"{GF2_CENTRE}_s100.pt")
    need(*cells.values(), cen1)
    v = {k: val_crps(p) for k, p in cells.items()}
    noise = abs(v[GF2_CENTRE] - val_crps(cen1))
    for k in sorted(v, key=v.get):
        L.append(f"  {k}: val CRPS {v[k]:.5f}  vs shipped {v[k] - v[GF2_CENTRE]:+.5f}")
    best = min(v, key=v.get)
    L.append(f"  seed noise {noise:.5f}; best {best}")
    if v[GF2_CENTRE] - v[best] > noise:
        pick("gf2", [best])
        return "PASS"
    return "KILL"


def gf2_follow(L):
    """GF2 follow-up REPORT (no gate of its own; New_Plan gives none): the picked cell at batch 16384, lr x 2, 12000 steps (gf2_big_s0)
    vs the picked cell at 3000 steps: validation CRPS. Its value goes to the loop session's decision on a full paired run."""
    best = read_pick("gf2")
    need(os.path.join(D, "gf2_big_s0.pt"))
    a, b = val_crps(os.path.join(D, f"{best[0]}_s0.pt")), val_crps(os.path.join(D, "gf2_big_s0.pt"))
    L.append(f"  {best[0]} 3000 steps {a:.5f}; batch 16384 / lr x2 / 12000 steps {b:.5f} ({b - a:+.5f})")
    return "REPORT"


# ---------------------------------------------------------------- GF4
def gf4(L):
    """GF4 PRE-SET RULE (CPU conditional calibration, scripts/s25_gf4_condcal.py writes models/s25/gf4_result.csv):
    gain = PIT TV (unstretched) - PIT TV (stretched) on 2024-25, mean over var x band, with the date-block (7-day) 95 % interval.
    KILL if the gain interval contains 0 (gain inside the date-block interval) or any var x band has a sign swap between the 2021 fit and the
    2022 fit (opposite signs with both |theta| > 0.05 on spread, stability or 500 hPa wind). Else PASS.
    Deviation: the plan scores against balloons; this uses ERA5 2024-25 (recorded in SECTION25_CODE_STATUS)."""
    p = os.path.join(D, "gf4_result.csv")
    need(p)
    r = pd.read_csv(p).set_index("key").value
    L.append(f"  PIT TV gain {r['gain']:+.5f} [{r['gain_lo']:+.5f}, {r['gain_hi']:+.5f}]; sign swaps {int(r['swaps'])}; cells {int(r['cells'])}")
    return "KILL" if r["gain_lo"] <= 0 or r["swaps"] > 0 else "PASS"


# ---------------------------------------------------------------- GF1 (+ GX2 in the screen)
GF1_ARMS = ["gf1_es0", "gf1_es03", "gf1_es1", "gf1_b05", "gf1_b15", "gf1_vario002", "gf1_vario005", "gf1_vario01", "gf1_svec005", "gf1_svec01", "gx2"]


def gf1_screen(L):
    """GF1 screen PRE-SET RULE: 11 arms (10 ES / variogram / shear-vector arms + the GX2 twES arm) at 3000 steps, seed 0, vs base3k s0
    (noise = |base3k s0 - s100|). Target = vcorr_sep + variogram composite on stack (b). An arm is eligible if it beats base3k by more than
    the noise and loses no more than 0.0009 skill15 (b). The best 2 eligible arms (lowest target) go to s25_gf1_pick.txt for 2-seed 6000-step
    runs. KILL if none is eligible."""
    tb = {s: composite(t_vcorr_vario, "base3k", s, "base3k") for s in SEEDS}
    noise = abs(tb[0] - tb[100])
    ok = {}
    for a in GF1_ARMS:
        n = a + "_3k"
        need(f_shape(n, 0, "b"), f_head(n, 0, "b"))
        t = composite(t_vcorr_vario, n, 0, "base3k")
        d = skill15(n, 0) - skill15("base3k", 0)
        el = tb[0] - t > noise and d >= -TOL
        L.append(f"  {n}: target {t:.4f} vs base3k {tb[0]:.4f} (noise {noise:.4f}); d_skill15(b) {d:+.4f}  {'eligible' if el else ''}")
        if el:
            ok[a] = t
    best = sorted(ok, key=ok.get)[:2]
    if not best:
        return "KILL"
    pick("gf1", best)
    L.append(f"  picks: {best}")
    return "PASS (screen)"


def gf1(L):
    """GF1 full PRE-SET RULE: each picked arm, 6000 steps, seeds 0 and 100, vs base: the 25.1 rule with target vcorr_sep + variogram on (b).
    Item verdict = best arm verdict (PASS > MISS > KILL). Also writes s25_gf1_moved.txt = YES if any arm's target beat noise in both seeds
    (the GX1 gate "GF1 moved (b) shape")."""
    picks = read_pick("gf1")
    if not picks:
        raise SystemExit("no GF1 picks: run gf1_screen first")
    vs, moved = [], False
    for a in picks:
        vs.append(paired_rule(a, "base", t_vcorr_vario, L))
        moved |= all(w[3] for w in target_wins(t_vcorr_vario, a, "base").values())
    pick("gf1_moved", ["YES" if moved else "NO"])
    return best_of(vs)


def best_of(vs):
    return "PASS" if "PASS" in vs else "MISS" if "MISS" in vs else "KILL"


# ---------------------------------------------------------------- GX2 / H4 (shear p99 after the shear-map refit)
def p99_up(name, base, L, min_up=0.03, min_bands=3):
    ok = []
    for s in SEEDS:
        a = pd.read_csv(f_shape(name, s, "b")).query("metric == 'shear_p99_ratio'").set_index("band").value
        b = pd.read_csv(f_shape(base, s, "b")).query("metric == 'shear_p99_ratio'").set_index("band").value
        up = (a - b).reindex(b.index)
        n = int((up >= min_up).sum())
        L.append(f"  {name} s{s} p99 ratio up: " + ", ".join(f"{k} {v:+.3f}" for k, v in up.items()) + f"  ({n} bands >= +{min_up})")
        ok.append(n >= min_bands)
    return all(ok)


def gx2(L):
    """GX2 PRE-SET RULE: twES on u, v over 0-18 km at q90 (twes_weight 0.1), 6000 steps, seeds 0 and 100, after the shear-map refit.
    KILL if the shear p99 ratio is not up by >= 0.03 in >= 3 of 4 bands in both seeds (vs base, stack b). Otherwise the 25.1 rule with the
    same p99 target (mean |ratio - 1|)."""
    if not p99_up("gx2", "base", L):
        return "KILL"
    return paired_rule("gx2", "base", t_p99, L)


def t_p99(name, s, stack="b", tag="cell8"):
    p99 = pd.read_csv(f_shape(name, s, stack, tag)).query("metric == 'shear_p99_ratio'").value
    return (float((p99 - 1).abs().mean()),)


def h4(L):
    """H4 PRE-SET RULE: EOF basis keeping 95 % variance + AR(1) noise across EOF index, seeds 0 and 100. KILL if the shear p99 ratio (after
    the shear-map refit) is not up by >= +0.03 in 3 bands, or skill15 (b) loses > 0.0009 in either seed. Otherwise the 25.1 rule (p99 target)."""
    if not p99_up("h4_eof", "base", L) or any(skill15("h4_eof", s) - skill15("base", s) < -TOL for s in SEEDS):
        return "KILL"
    return paired_rule("h4_eof", "base", t_p99, L)


# ---------------------------------------------------------------- GT2
def gt2(L):
    """GT2 PRE-SET RULE: pool = shipped-style base members + il8b token members (d 96, 3000 steps) and the IL-23 pool (scripts/s25_pool.py),
    seeds 0 and 100. PASS if pool skill15 (b) >= base + 0.0006 in both seeds and compare_shape is not WORSE in either seed. Else KILL."""
    ok = True
    for s in SEEDS:
        d = skill15("gt2_pool", s) - skill15("base", s)
        g = gates("gt2_pool", s, "base")
        L.append(f"  gt2_pool s{s}: d_skill15(b) {d:+.4f}; shape {'FAIL ' + g['shape_worse'] if g['shape_fail'] else 'ok'}; Denver {denver('gt2_pool', s)} (report)")
        ok &= d >= 0.0006 and not g["shape_fail"]
    return "PASS" if ok else "KILL"


# ---------------------------------------------------------------- GF3 / MF2
def flowlike(L, arms, item):
    """Shared GF3 / MF2 rule. KILL if every listed arm loses > 0.0009 skill15 (b) in a seed, or no arm's (b) shape target (vcorr_err + Ri<1
    gap 12-18 km) beats the base by more than noise in both seeds. PASS if any arm passes the 25.1 rule with that target on (a) and (b)."""
    lose = all(any(skill15(a, s) - skill15("base", s) < -TOL for s in SEEDS) for a in arms)
    shape_better = any(all(w[3] for w in target_wins(t_gf3, a, "base").values()) for a in arms)
    vs = [paired_rule(a, "base", t_gf3_ab, L) for a in arms]
    if lose or not shape_better:
        return "KILL"
    v = best_of(vs)
    pick(item, [a for a, x in zip(arms, vs) if x == "PASS"] or [a for a, x in zip(arms, vs) if x == "MISS"])
    return v


def gf3(L):
    """GF3 PRE-SET RULE: F1 = flow matching (gf3_f1), F2 = F1 + 1000 steps afCRPS on 4-step samples (gf3_f2), seeds 0 and 100; F3 = F1 scored
    with the shuffle OFF (reported only). KILL if F1 and F2 both lose > 0.0009 skill15, or (b) shape is not better than shipped (target
    vcorr_err + |Ri<1 - truth| 12-18 km beats base by more than noise in both seeds for neither arm). Targets on (a) and (b).
    PASS = an arm passes the 25.1 rule; else MISS. The PASS / MISS arm is the MF1 teacher (s25_gf3_pick.txt). Sampler cost from s25_sampler_cost.log."""
    v = flowlike(L, ["gf3_f1", "gf3_f2"], "gf3")
    for s in SEEDS:
        if os.path.exists(f_diag("gf3_f1", s, "b", "noshuf")):
            L.append(f"  F3 (shuffle off) s{s}: vcorr_err {shape_val('gf3_f1', s, 'b', 'vcorr_err', tag='noshuf', src='diag'):.4f}"
                     f" vs F1 {shape_val('gf3_f1', s, 'b', 'vcorr_err', src='diag'):.4f}; skill15 {skill15('gf3_f1', s, tag='noshuf'):.4f} (report)")
    cost = os.path.join(K.LOGS, "s25_sampler_cost.log")
    if os.path.exists(cost):
        with open(cost, encoding="utf-8") as fh:
            L.extend("  cost: " + x.rstrip() for x in fh if x.strip())
    return v


def mf2(L):
    """MF2 PRE-SET RULE: RML generator with K = 3 and K = 5 refinement passes, seeds 0 and 100. Same rule as GF3 (flowlike): KILL if both
    lose > 0.0009 skill15 or (b) shape target not better than shipped by more than noise; PASS = an arm passes the 25.1 rule; else MISS."""
    return flowlike(L, ["mf2_k3", "mf2_k5"], "mf2")


# ---------------------------------------------------------------- GX1 / GT1 / H3 / H2
def gx1(L):
    """GX1 PRE-SET RULE (gate: s25_gf1_moved.txt = YES): signature loss (sig_weight 0.05), and the every-2nd-height variant, seeds 0 and 100;
    the 25.1 rule with target vcorr_sep + variogram on (b). Item verdict = best arm."""
    if read_pick("gf1_moved") != ["YES"]:
        L.append("  gate closed: GF1 did not move (b) shape")
        return "SKIPPED (gate)"
    return best_of([paired_rule(a, "base", t_vcorr_vario, L) for a in ("gx1", "gx1_s2")])


def gt1(L):
    """GT1 PRE-SET RULE: height-autoregressive generator, 7 blocks, seeds 0 and 100; the 25.1 rule with target vcorr error across
    neighbouring blocks + mean |shear p99 ratio - 1| on (b). Error (normalised CRPS) per block is reported."""
    for s in SEEDS:
        a = pd.read_csv(f_shape("gt1", s, "b")).query("metric == 'block_crps'").set_index("band").value
        b = pd.read_csv(f_shape("base", s, "b")).query("metric == 'block_crps'").set_index("band").value
        L.append(f"  gt1 s{s} block CRPS / sd (gt1 - base): " + ", ".join(f"{k} {a[k]:.4f} ({a[k] - b.get(k, np.nan):+.4f})" for k in a.index))
    return paired_rule("gt1", "base", t_gt1, L)


def h3(L):
    """H3 PRE-SET RULE: mixture of 3 experts with a learned gate, seeds 0 and 100. KILL on gate collapse (one expert > 90 % weight on > 90 %
    of rows, from scripts/s25_gate_month.py -> models/s25/h3_moe_sSEED_gate.csv) or target inside seed noise; else the 25.1 rule with
    target vcorr_sep + variogram. Gate weights by month are reported."""
    collapse = False
    for s in SEEDS:
        p = os.path.join(D, f"h3_moe_s{s}_gate.csv")
        need(p)
        g = pd.read_csv(p)
        c = bool(g.loc[g.month.astype(str) == "all", "collapse"].iloc[0])
        collapse |= c
        L.append(f"  h3 s{s} gate by month:\n" + g.round(3).to_string(index=False) + f"\n  collapse {c}")
    v = paired_rule("h3_moe", "base", t_vcorr_vario, L)
    return "KILL" if collapse else v


def h2(L):
    """H2 PRE-SET RULE: analog-ensemble member source, k = 8, own year excluded, table <= 200 MB, seeds 0 and 100. KILL if skill15 (b) is
    more than 0.0015 worse AND shape is not better (target vcorr_sep + variogram inside noise) in (b), in either seed. Otherwise the 25.1 rule.
    Shuffle-OFF vcorr is reported."""
    wins = target_wins(t_vcorr_vario, "h2_analog", "base")
    for s in SEEDS:
        if skill15("h2_analog", s) - skill15("base", s) < -0.0015 and not wins[s][3]:
            L.append(f"  s{s}: skill15 > 0.0015 worse and shape not better")
            return "KILL"
        if os.path.exists(f_shape("h2_analog", s, "b", "noshuf")):
            L.append(f"  h2 s{s} shuffle OFF vcorr_sep {shape_val('h2_analog', s, 'b', 'vcorr_sep', tag='noshuf'):.4f}"
                     f" (shuffle on {shape_val('h2_analog', s, 'b', 'vcorr_sep'):.4f}) (report)")
    return paired_rule("h2_analog", "base", t_vcorr_vario, L)


# ---------------------------------------------------------------- MF1 / H1 / H5
def mf1(L):
    """MF1 PRE-SET RULE (gate: GF3 PASS or MISS, teacher = the s25_gf3_pick.txt arm): student = shipped-size MLP distilled from the flow
    teacher (distill_m 8), seeds 0 and 100. PASS if in both seeds skill15 (b) is within 0.0005 of the teacher's AND the student keeps >= 70 %
    of the teacher's shape gain over base (gain = base target - arm target, target vcorr_err + |Ri<1 - truth| 12-18 km on (a) and (b)).
    Else KILL."""
    t = read_pick("gf3")
    if not t:
        L.append("  gate closed: GF3 has no PASS / near-miss arm")
        return "SKIPPED (gate)"
    ok = True
    for s in SEEDS:
        tb = composite(t_gf3_ab, "base", s, "base")
        gt, gs = tb - composite(t_gf3_ab, t[0], s, "base"), tb - composite(t_gf3_ab, "mf1", s, "base")
        d = skill15("mf1", s) - skill15(t[0], s)
        keep = gs / gt if gt > 0 else np.nan
        L.append(f"  mf1 s{s} vs teacher {t[0]}: d_skill15 {d:+.4f}; shape gain kept {keep:.2f}")
        ok &= abs(d) <= 0.0005 and gt > 0 and keep >= 0.70
    return "PASS" if ok else "KILL"


def h1(L):
    """H1 PRE-SET RULE: prior (GRAM-style Gaussian from training rows) + learned residual vs the same model fed N(0, 1) (control h1_noise),
    seeds 0 and 100. KILL if the prior ties the control in either seed (neither skill15 (b) better by more than the skill15 seed noise nor the
    vcorr_sep + variogram target better by more than its noise). Otherwise the 25.1 rule vs base."""
    nz_sk = abs(skill15("base", 0) - skill15("base", 100))
    tb = {s: composite(t_vcorr_vario, "base", s, "base") for s in SEEDS}
    nz_t = abs(tb[0] - tb[100])
    for s in SEEDS:
        dsk = skill15("h1_prior", s) - skill15("h1_noise", s)
        dt = composite(t_vcorr_vario, "h1_noise", s, "base") - composite(t_vcorr_vario, "h1_prior", s, "base")
        L.append(f"  s{s} prior - control: skill15 {dsk:+.4f} (noise {nz_sk:.4f}), target gain {dt:+.4f} (noise {nz_t:.4f})")
        if not (dsk > nz_sk or dt > nz_t):
            return "KILL"
    return paired_rule("h1_prior", "base", t_vcorr_vario, L)


def h5(L):
    """H5 PRE-SET RULE: draft (base members) + flow refine from tau0 = 0.2 / 0.4 with 2-3 steps (scripts/s25_compose_refine.py), seeds 0 and
    100, vs the draft alone (= base). KILL if the shape gain vs the draft (vcorr_sep + variogram on (b)) is inside seed noise in either seed,
    or skill15 (b) goes down vs the draft by more than 0.0009 in either seed. Else PASS. Item verdict = best tau0 arm."""
    vs = []
    for a in ("h5_t02", "h5_t04"):
        w = target_wins(t_vcorr_vario, a, "base")
        dk = [skill15(a, s) - skill15("base", s) for s in SEEDS]
        for s, dd in zip(SEEDS, dk):
            L.append(f"  {a} s{s}: target {w[s][0]:.4f} vs draft {w[s][1]:.4f} (noise {w[s][2]:.4f}); d_skill15 {dd:+.4f}; Denver {denver(a, s)} (report)")
        vs.append("PASS" if all(x[3] for x in w.values()) and min(dk) >= -TOL else "KILL")
    return "PASS" if "PASS" in vs else "KILL"


def n1c4w(L, name="n1c4w"):
    """N1C4W PRE-SET RULE (New_Plan 28.8 step 1, written before the run): N1 cross-fitted members on the c4w recipe vs the paired base, seeds
    0 and 100. Target = mean skill15 (unknown drivers) on stack (b), higher is better; noise = |base_s0 - base_s100| of it. KILL if the gain
    is inside noise in either seed or any shape FAIL; PASS if preclip and cov99 gates also hold in both seeds (the -0.0009 skill gate is
    implied by the target); else MISS. A PASS keeps N1 in the 28.3 stack; the AV34 trust refit (step 2) then runs on it."""
    nz = abs(skill15("base", SEEDS[0]) - skill15("base", SEEDS[1]))
    gs = {s: gates(name, s, "base") for s in SEEDS}
    beats = {}
    for s in SEEDS:
        a, b, g = skill15(name, s), skill15("base", s), gs[s]
        beats[s] = a - b > nz
        L.append(f"  {name} s{s}: skill15(b) {a:.4f} vs base {b:.4f} ({a - b:+.4f}, noise {nz:.4f}) {'beats' if beats[s] else 'inside noise'}; "
                 f"shape {'FAIL ' + g['shape_worse'] if g['shape_fail'] else 'ok'}; preclip {g['preclip']:+.5f} {'ok' if g['preclip_ok'] else 'FAIL'}; "
                 f"cov99 {'ok' if g['cov_ok'] else 'FAIL'}; Denver skill15 {denver(name, s)} vs base {denver('base', s)} (report)")
    if any(g["shape_fail"] for g in gs.values()) or not all(beats.values()):
        return "KILL"
    return "PASS" if all(g["preclip_ok"] and g["cov_ok"] for g in gs.values()) else "MISS"


def av34s25(L):
    """AV34S25 PRE-SET RULE (New_Plan 28.8 step 2, written 2026-11-19 23:30 before the run): the AV34 trust layer (min-gain 0.001, AV34 skips)
    refit on the paired base (N1 dropped at step 1, so the stack is unchanged), stack (b) with --trust vs base, seeds 0 and 100. Same rule as
    step 1: KILL if the skill15 (b) gain is inside base seed noise in either seed or any shape FAIL; PASS if preclip and cov99 also hold in both
    seeds; else MISS. A PASS keeps the trust layer in the 28.3 stack; step 3 (AV19) then runs on it."""
    return n1c4w(L, "av34s25")


def av19s25(L, name="av19s25", ref="base"):
    """AV19S25 PRE-SET RULE (New_Plan 28.8 step 3, written 2026-11-20 00:35 before the run): Student-t noise (8 dims, nu 4, head 4) on the c4w
    paired-base recipe (configs/s25/av19.toml), seeds 0 and 100, vs base (steps 1 and 2 dropped, so the stack is the base). AV19's own target is
    Denver: Denver skill15 (unknown, range map only) gain > noise |base_s0 - base_s100| of it in both seeds, else KILL; any shape FAIL -> KILL;
    PASS if also NM/TX skill15 (b) loss <= 0.0009, preclip and cov99 ok in both seeds; else MISS. A PASS keeps it; step 4 (AV35) then runs on it."""
    def den(n, s):
        p = os.path.join(D, f"{n}_s{s}_den_cal2021_headline.csv")
        need(p)
        return float(pd.read_csv(p).skill15_unknown.mean())
    nz = abs(den("base", SEEDS[0]) - den("base", SEEDS[1]))
    gs = {s: gates(name, s, ref) for s in SEEDS}
    beats, nmtx = {}, {}
    for s in SEEDS:
        a, b, g = den(name, s), den(ref, s), gs[s]
        beats[s] = a - b > nz
        nmtx[s] = skill15(name, s) - skill15(ref, s) >= -0.0009
        L.append(f"  {name} s{s}: Denver skill15 {a:.4f} vs {ref} {b:.4f} ({a - b:+.4f}, noise {nz:.4f}) {'beats' if beats[s] else 'inside noise'}; "
                 f"NM/TX skill15(b) {skill15(name, s) - skill15(ref, s):+.4f} {'ok' if nmtx[s] else 'FAIL'}; "
                 f"shape {'FAIL ' + g['shape_worse'] if g['shape_fail'] else 'ok'}; preclip {g['preclip']:+.5f} {'ok' if g['preclip_ok'] else 'FAIL'}; "
                 f"cov99 {'ok' if g['cov_ok'] else 'FAIL'}")
    if any(g["shape_fail"] for g in gs.values()) or not all(beats.values()):
        return "KILL"
    return "PASS" if all(nmtx.values()) and all(g["preclip_ok"] and g["cov_ok"] for g in gs.values()) else "MISS"



def x4s25(L):
    """X4S25 PRE-SET RULE (New_Plan 28.9, 28.4 MISS-idea arm, written 2026-11-20 01:35 before the run): AV40 climatology-mean anomaly output with
    RH kept plain (configs/s25/x4.toml), seeds 0 and 100, Denver scored with the table refit on Denver rows <= 2020 (s25_arm.sh ANOM_DEN=1).
    Compared against the 28.3 stack S25_STACK (base, or av19s25 if AV19 passed; the runner sets it and stacks AV19's keys). Same rule as av19s25:
    Denver skill15 gain over the stack > base Denver seed noise in both seeds and no shape FAIL, else KILL; PASS if also NM/TX skill15 (b) loss
    <= 0.0009 and preclip / cov99 ok in both seeds; else MISS. Overfit guard: 2024-25 is the only period here, so a PASS is "development period only"."""
    return av19s25(L, "x4s25", os.environ.get("S25_STACK", "base"))


def x4bs25(L):
    """X4BS25 PRE-SET RULE (New_Plan 28.10 step 2, written 2026-11-20 04:58 before the run): X4 variant b (configs/s25/x4b.toml: climatology-mean
    anomaly, RH and v plain, offset x0.5), seeds 0 and 100, Denver with the table refit on Denver rows <= 2020, vs the base (AV19 KILL).
    Same rule as x4s25 / av19s25: Denver skill15 gain > base Denver seed noise in both seeds and no shape FAIL, else KILL; PASS if also NM/TX
    skill15 (b) loss <= 0.0009 and preclip / cov99 ok in both seeds; else MISS. The variant was picked from the x4s25 failure mode (not tuned on
    2024-25 scores), and the 2026 final test stays the untouched holdout."""
    return av19s25(L, "x4bs25", "base")


def x4cs25(L):
    """X4CS25 PRE-SET RULE (New_Plan 28.10 step 2, written 2026-11-20 07:05 before the run, only run if x4bs25 is KILL): X4 variant c
    (configs/s25/x4c.toml: climatology-mean anomaly, RH, v and rh2m plain, offset x0.25), seeds 0 and 100, Denver table refit on Denver rows
    <= 2020, vs the base. Same rule as x4bs25: Denver skill15 gain > base Denver seed noise in both seeds and no shape FAIL, else KILL; PASS if
    also NM/TX skill15 (b) loss <= 0.0009 and preclip / cov99 ok in both seeds; else MISS."""
    return av19s25(L, "x4cs25", "base")


ITEMS = dict(gf2=gf2, gf2_follow=gf2_follow, gf4=gf4, gf1_screen=gf1_screen, gf1=gf1, gx2=gx2, gt2=gt2, gf3=gf3, mf2=mf2, gx1=gx1,
             gt1=gt1, mf1=mf1, h1=h1, h3=h3, h4=h4, h2=h2, h5=h5, n1c4w=n1c4w, av34s25=av34s25, av19s25=av19s25, x4s25=x4s25, x4bs25=x4bs25, x4cs25=x4cs25)


def judge(item):
    L = [f"S25 {item.upper()} ({ITEMS[item].__doc__.split(':')[0].strip()})"]
    v = ITEMS[item](L)
    L.append(f"VERDICT (pre-set rule): {v}")
    K.report(f"s25_{item}", L)
    return v


# ---------------------------------------------------------------- self-check on synthetic files (KIT_SMOKE: nothing logged)
def _fake(name, s, sk, vc, p99=1.0, pre=0.001, tag="cell8", vario=1.0, ri=0.1):
    bands = [b for b, _, _ in K.BANDS]
    rows = [dict(var=v, band=b, skill15_unknown=sk, skill15_unknown_lo=sk - 0.0001, skill15_unknown_hi=sk + 0.0001, cov99_unknown=0.99,
                 cov99_unknown_lo=0.989, cov99_unknown_hi=0.991, mae_unknown=1.0) for v in ("u", "v", "T") for b in bands]
    for st in ("a", "b"):
        pd.DataFrame(rows).to_csv(f_head(name, s, st, tag), index=False)
        dg = [dict(metric=m, var="u", band=b, value=(vc if m == "vcorr_err" else pre if m == "preclip_rate" else 0.05), goal=None)
              for m in CS.METRICS for b in bands]
        pd.DataFrame(dg).to_csv(f_diag(name, s, st, tag), index=False)
        sh = [dict(metric="vcorr_sep", var="u", band="0-1 km", value=vc), dict(metric="variogram", var="u", band="all", value=vario)]
        sh += [dict(metric="shear_p99_ratio", var="shear", band=b, value=p99) for b in bands]
        sh += [dict(metric="ri_lt1_share", var="ri", band=b, value=ri) for b in bands] + [dict(metric="ri_lt1_truth", var="ri", band=b, value=0.05) for b in bands]
        sh += [dict(metric="block_crps", var="block", band=f"b{i}", value=0.5) for i in range(7)]
        sh += [dict(metric="vcorr_nbr", var="block", band=f"b{i}-b{i + 1}", value=vc) for i in range(6)]
        pd.DataFrame(sh).to_csv(f_shape(name, s, st, tag), index=False)


def _selfcheck():
    import tempfile
    global D
    os.environ["KIT_SMOKE"] = "1"
    old_logs, D = K.LOGS, tempfile.mkdtemp()
    K.LOGS = D
    try:
        for s, n in ((0, 0.100), (100, 0.101)):
            _fake("base", s, 0.30, n)
            _fake("good", s, 0.30, 0.080, p99=1.05, vario=0.9)
            _fake("tie", s, 0.30, n + 0.0002)
            _fake("lossy", s, 0.29, 0.080, vario=0.9)
            _fake("bad_shape", s, 0.30, 0.300)
        L = []
        assert paired_rule("good", "base", t_vcorr_vario, L) == "PASS", L
        assert paired_rule("tie", "base", t_vcorr_vario, L) == "KILL"
        assert paired_rule("lossy", "base", t_vcorr_vario, L) == "MISS"
        assert paired_rule("bad_shape", "base", t_vcorr_vario, L) == "KILL"
        for s, sk in ((0, 0.31), (100, 0.31)):
            _fake("n1up", s, sk, 0.100 if s == 0 else 0.101)
        assert n1c4w(L, "n1up") == "PASS" and n1c4w(L, "tie") == "KILL" and n1c4w(L, "bad_shape") == "KILL"
        assert p99_up("good", "base", L) and not p99_up("tie", "base", L)
        import torch
        for k in [f"gf2_l{a}_w{b}" for a in GF2_LR for b in GF2_WD]:
            v = 0.40 if k == "gf2_l3e-3_w1e-5" else 0.50
            torch.save({"members": [{"history": [(500, 1.0, v + 0.01), (1000, 1.0, v)]}]}, os.path.join(D, f"{k}_s0.pt"))
        torch.save({"members": [{"history": [(1000, 1.0, 0.501)]}]}, os.path.join(D, f"{GF2_CENTRE}_s100.pt"))
        assert gf2(L) == "PASS" and read_pick("gf2") == ["gf2_l3e-3_w1e-5"]
        torch.save({"members": [{"history": [(1000, 1.0, 0.45)]}]}, os.path.join(D, "gf2_l3e-3_w1e-5_s0.pt"))
        torch.save({"members": [{"history": [(1000, 1.0, 0.30)]}]}, os.path.join(D, f"{GF2_CENTRE}_s100.pt"))   # noise 0.2 swamps every gain
        assert gf2(L) == "KILL"
        pd.DataFrame(dict(key=["gain", "gain_lo", "gain_hi", "swaps", "cells"], value=[0.01, 0.002, 0.02, 0, 12])).to_csv(os.path.join(D, "gf4_result.csv"), index=False)
        assert gf4(L) == "PASS"
        pd.DataFrame(dict(key=["gain", "gain_lo", "gain_hi", "swaps", "cells"], value=[0.01, 0.002, 0.02, 1, 12])).to_csv(os.path.join(D, "gf4_result.csv"), index=False)
        assert gf4(L) == "KILL"
    finally:
        K.LOGS = old_logs
    print("s25_judges selfcheck ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
    elif len(sys.argv) == 2 and sys.argv[1] in ITEMS:
        judge(sys.argv[1])
    else:
        raise SystemExit(__doc__)
