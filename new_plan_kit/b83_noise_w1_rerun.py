"""26.1 step 1 (2026-11-19), part 1: re-measure the old shear-stretch MISSes (W1, W5, W6) on the enlarged case set (600 cases per site, EPZ + MAF, 2024-25, balloon-corrected as b81/b82), one tool run for all three.
V5a and W2 (u,v copula) are separate scripts (not here). Same fit/test split as b81 (odd-index fit, even-index test), same variants (W1 plain, W5 W1_NOSHRINK, W6 NOSHRINK + TAPER).
PRE-SET RULE (before the run): INFORMATIVE if the 95 % interval (whole days) of (arm - shipped) vertical-corr error is narrower than 0.01. An arm PASSES on a seed if it is informative and passes the b81 limits on the test cases:
(a) shear p99 ratio 0.90-1.10 in all 4 bands, (b) CRPS u, v, T not worse than shipped by over 0.3 %, (c) vertical-corr error not worse than shipped by over 0.003, (d) Ri<1 share 12-18 km not farther from balloons than shipped (or within 0.01). Else MISS.
Any arm passing on both seeds (KIT_SEED 0 and 1) goes to ASK_LATER as a possible PASS (never shipped). Not informative -> the width is reported and the old MISS stands.
    PYTHONPATH=".;new_plan_kit" KIT_SEED=0 .venv/Scripts/python -W ignore new_plan_kit/b83_noise_w1_rerun.py     Result: docs/results/logs/kit_b83_noise_w1_rerun.log
"""
import argparse
import os

import numpy as np

import kit_common as K
import b9_gram_compare as B9
import b81_w1_shear_stretch as W
from b1_shape_scores import ri_counts
from b82_t2_heldout import STN, pos

NM = 50
VARS = B9.VARS


def fit_f(C, fit, taper, noshrink):
    os.environ.pop("W1_TAPER", None)
    if taper:
        os.environ["W1_TAPER"] = "1"
    sb = np.concatenate([K.shear_mag(C[i][2]["u"], C[i][2]["v"])[None] for i in fit])
    pb = W.p99(sb)
    f = np.ones(4)
    for _ in range(4):
        sm = np.concatenate([K.shear_mag(*(W.stretch(C[i][3], f)[q] for q in ("u", "v"))) for i in fit])
        f = np.clip(f * pb / W.p99(sm), 0.5, 3.0)
    return np.maximum(f, 1.0) if noshrink else f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-station", type=int, default=600)
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    seed = int(os.environ.get("KIT_SEED", 0))
    rng = np.random.default_rng(seed)
    C = []                                   # (day, clim mean, balloon dict, members dict)
    for name in ("EPZ", "MAF"):
        sid, (y0, y1) = STN[name]
        lat, lon, elev = pos(sid)
        t, b = K.balloon(sid)
        full = np.isfinite(b["u"]).sum(1) >= 30
        idx = np.flatnonzero((t.year >= y0) & (t.year <= y1) & np.isin(t.hour, (0, 12)) & full)
        n0 = len(C)
        for k in rng.permutation(idx)[:int(a.per_station * 1.15)]:
            if len(C) - n0 >= a.per_station:
                break
            mu, _ = B9.clim_stats(sid, t[k].month, t[k].hour)
            try:
                run = K.tool(lat, lon, t[k], seed=1000 * t[k].year + int(t[k].dayofyear), n=NM, elevation=elev)
            except ValueError:
                continue
            C.append((f"{name}{t[k]:%Y-%m-%dT%H}", mu, {q: b[q][k] for q in b}, {q: np.asarray(run[q], float) for q in (*VARS, "p")}))
        print(f"{name}: {len(C) - n0} cases", flush=True)
    n = len(C)
    assert n >= 8, f"only {n} cases"
    # interleave stations so odd/even parity splits both
    order = rng.permutation(n)
    C = [C[i] for i in order]
    fit = [i for i in range(n) if i % 2 == 0]
    te = [i for i in range(n) if i % 2 == 1]
    nt = len(te)
    arms = {"W1": (False, False), "W5": (False, True), "W6": (True, True)}
    S = {"shipped": [C[i][3] for i in te]}
    fs = {}
    for k, (tap, ns) in arms.items():
        fs[k] = fit_f(C, fit, tap, ns)
        os.environ.pop("W1_TAPER", None)
        if tap:
            os.environ["W1_TAPER"] = "1"
        S[k] = [W.stretch(C[i][3], fs[k]) for i in te]
    os.environ.pop("W1_TAPER", None)
    days = np.array([C[i][0] for i in te])
    js = np.random.default_rng(seed + 77).integers(NM, size=nt)
    pick = {s: {q: np.array([S[s][k][q][js[k]] - C[te[k]][1][q] for k in range(nt)]) for q in VARS} for s in S}
    bal = {q: np.array([C[i][2][q] - C[i][1][q] for i in te]) for q in VARS}
    crps = {s: {q: np.mean([np.nanmean(B9.crps_cols(S[s][k][q], C[te[k]][2][q])) for k in range(nt)]) for q in VARS} for s in S}
    sbt = np.concatenate([K.shear_mag(C[i][2]["u"], C[i][2]["v"])[None] for i in te])
    r99, ri = {}, {}
    for s in S:
        sh = np.concatenate([K.shear_mag(x["u"], x["v"]) for x in S[s]])
        r99[s] = W.p99(sh) / W.p99(sbt)
        c = np.zeros((4, 2))
        for x in S[s]:
            c += ri_counts(x["u"], x["v"], x["T"], x["p"])
        ri[s] = c[:, 0] / np.maximum(c[:, 1], 1)
    cb = np.zeros((4, 2))
    for i in te:
        b = C[i][2]
        cb += ri_counts(b["u"], b["v"], b["T"], b["p"])
    rib = cb[:, 0] / np.maximum(cb[:, 1], 1)
    err = lambda s, i: B9.vert_err({q: pick[s][q][i] for q in VARS}, {q: bal[q][i] for q in VARS})
    every = np.arange(nt)
    L = [f"26.1 step 1a W1/W5/W6 rerun (seed {seed}): {n} cases (EPZ + MAF), fit {len(fit)}, test {nt}, {NM} members",
         "source    vertical-corr err   CRPS u v T            shear p99 ratio per band   Ri<1 per band"]
    for s in S:
        L.append(f"  {s:<8} {err(s, every):<8.3f} " + " ".join(f"{crps[s][q]:<6.3f}" for q in VARS) + "  " + " ".join(f"{x:.2f}" for x in r99[s]) + "   " + " ".join(f"{x:.3f}" for x in ri[s]))
    L.append(f"  balloons ri " + " ".join(f"{x:.3f}" for x in rib))
    for k in arms:
        d = B9.boot(lambda i: err(k, i) - err("shipped", i), days, a.boot)
        w = d[2] - d[1]
        cr = {q: 100 * (crps[k][q] / crps["shipped"][q] - 1) for q in VARS}
        ok = {"informative (width < 0.01)": w < 0.01,
              "p99 0.90-1.10": bool(np.all(np.abs(r99[k] - 1) <= 0.10)),
              "CRPS <= +0.3 %": all(v <= 0.3 for v in cr.values()),
              "vcorr not worse by > 0.003": err(k, every) - err("shipped", every) <= 0.003,
              "Ri<1 12-18 km": abs(ri[k][3] - rib[3]) <= max(abs(ri["shipped"][3] - rib[3]), 0.01)}
        L.append(f"{k}: f " + " ".join(f"{x:.2f}" for x in fs[k]) + f"; err vs shipped {d[0]:+.4f} [{d[1]:+.4f}, {d[2]:+.4f}] width {w:.4f}; CRPS " + " ".join(f"{q} {v:+.2f} %" for q, v in cr.items()) + "; " + "; ".join(f"{x} {'ok' if v else 'FAIL'}" for x, v in ok.items()))
        L.append(f"VERDICT {k} (pre-set rule, this seed): " + ("PASS" if all(ok.values()) else "MISS"))
    L.append("Notes: development window (2024-25), tool balloon-corrected, not a blind test. Both seeds must pass; PASS -> ASK_LATER only.")
    K.report("b83_noise_w1_rerun", L)


if __name__ == "__main__":
    main()
