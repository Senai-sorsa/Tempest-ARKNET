"""26.2 (2026-11-19): W2 copula (u,v ranks, maps on) + damped shear stretch at 12-18 km only (factor 1 below 12 km = copied back), tool shipped as control.
Cases b9 list (EPZ / MAF, 00Z / 12Z, 2024-25, --per-group cases per group, default 450 = 1800), 50 members. f (12-18 km) fit on even-index cases so the pooled shear p99 matches the balloons, tested on odd-index cases.
PRE-SET RULE (written before the run; both seeds KIT_SEED 0 and 1 needed): PASS if on the test cases
 (a) vertical-corr error <= 0.047 AND the 95 % interval (whole days) of (arm - shipped) error lies below 0 (upper end < 0),
 (b) CRPS u, v, T not worse than shipped by over 0.3 %,
 (c) shear p99 ratio 0.90-1.10 in all four bands,
 (d) Ri<1 share 12-18 km within 0.03 of the balloons and not farther from them than shipped.
Else MISS and close. PASS -> ASK_LATER only, never shipped.
    PYTHONPATH=".;new_plan_kit" KIT_SEED=0 .venv/Scripts/python -W ignore new_plan_kit/b84_combined_copula_stretch.py [--per-group 450]   Result: docs/results/logs/kit_b84_combined_copula_stretch.log
"""
import argparse
import os

import numpy as np

import kit_common as K
import b9_gram_compare as B9
import b79_w2_copula_uv as W2
import b81_w1_shear_stretch as W
from b1_shape_scores import ri_counts

NM = 50
VARS = B9.VARS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=450)
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    from tempest_weather import api
    A = api._assets()
    seed = int(os.environ.get("KIT_SEED", 0))
    rng = np.random.default_rng(seed)
    trng = np.random.default_rng(5 + seed)
    C, skipped = [], 0
    for cid, sid, t, b in B9.cases(a.per_group, rng):
        lat, lon, elev = K.station_pos(sid)
        mu, _ = B9.clim_stats(sid, t.month, t.hour)
        cseed = 1000 * t.year + int(t.dayofyear)
        try:
            ranks, _, _ = W2.balloon_ranks(sid, t.month, t.hour, trng)
            ship = K.tool(lat, lon, t, seed=cseed, n=NM, elevation=elev)
            cop = W2.run_arm(api, A, W2.ARMS[1], t.month - 1, ranks, lat, lon, t, elev, cseed)
        except ValueError:
            skipped += 1
            continue
        C.append((f"{t:%Y-%m-%d}", mu, b, {q: np.asarray(ship[q], float) for q in (*VARS, "p")}, {q: np.asarray(cop[q], float) for q in (*VARS, "p")}))
    n = len(C)
    assert n >= 8, f"only {n} cases"
    fit = [i for i in range(n) if i % 2 == 0]
    te = [i for i in range(n) if i % 2 == 1]
    nt = len(te)
    pb = W.p99(np.concatenate([K.shear_mag(C[i][2]["u"], C[i][2]["v"])[None] for i in fit]))
    f = np.ones(4)
    for _ in range(4):
        sm = np.concatenate([K.shear_mag(*(W.stretch(C[i][4], f)[q] for q in ("u", "v"))) for i in fit])
        g = np.clip(f * pb / W.p99(sm), 0.5, 3.0)
        f[3] = g[3]                                          # only 12-18 km moves; bands below stay 1 (copied back)
    S = {"shipped": [C[i][3] for i in te], "W2 copula": [C[i][4] for i in te], "combined": [W.stretch(C[i][4], f) for i in te]}
    days = np.array([C[i][0] for i in te])
    js = np.random.default_rng(seed + 77).integers(NM, size=nt)
    pick = {s: {q: np.array([S[s][k][q][js[k]] - C[te[k]][1][q] for k in range(nt)]) for q in VARS} for s in S}
    bal = {q: np.array([C[i][2][q] - C[i][1][q] for i in te]) for q in VARS}
    crps = {s: {q: np.mean([np.nanmean(B9.crps_cols(S[s][k][q], C[te[k]][2][q])) for k in range(nt)]) for q in VARS} for s in S}
    sbt = np.concatenate([K.shear_mag(C[i][2]["u"], C[i][2]["v"])[None] for i in te])
    r99, ri = {}, {}
    for s in S:
        r99[s] = W.p99(np.concatenate([K.shear_mag(x["u"], x["v"]) for x in S[s]])) / W.p99(sbt)
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
    L = [f"26.2 combined copula + damped stretch 12-18 km (seed {seed}): {n} cases ({skipped} skipped), fit {len(fit)}, test {nt}, {NM} members; f per band " + " ".join(f"{x:.2f}" for x in f),
         "source      vertical-corr err   CRPS u v T            shear p99 ratio per band   Ri<1 per band"]
    for s in S:
        L.append(f"  {s:<10} {err(s, every):<8.3f} " + " ".join(f"{crps[s][q]:<6.3f}" for q in VARS) + "  " + " ".join(f"{x:.2f}" for x in r99[s]) + "   " + " ".join(f"{x:.3f}" for x in ri[s]))
    L.append("  balloons ri " + " ".join(f"{x:.3f}" for x in rib))
    k = "combined"
    d = B9.boot(lambda i: err(k, i) - err("shipped", i), days, a.boot)
    cr = {q: 100 * (crps[k][q] / crps["shipped"][q] - 1) for q in VARS}
    ok = {"error <= 0.047": err(k, every) <= 0.047, "vs shipped interval below 0": d[2] < 0,
          "CRPS <= +0.3 %": all(v <= 0.3 for v in cr.values()),
          "p99 0.90-1.10 all bands": bool(np.all(np.abs(r99[k] - 1) <= 0.10)),
          "Ri<1 12-18 km within 0.03 and not farther than shipped": abs(ri[k][3] - rib[3]) <= 0.03 and abs(ri[k][3] - rib[3]) <= abs(ri["shipped"][3] - rib[3])}
    L.append(f"{k}: err vs shipped {d[0]:+.4f} [{d[1]:+.4f}, {d[2]:+.4f}]; CRPS " + " ".join(f"{q} {v:+.2f} %" for q, v in cr.items()) + "; " + "; ".join(f"{x} {'ok' if v else 'FAIL'}" for x, v in ok.items()))
    L.append("VERDICT (pre-set rule, this seed): " + ("PASS" if all(ok.values()) else "MISS"))
    L.append("Notes: development window (2024-25), tool balloon-corrected, templates from the same station's balloons: not a blind test. Both seeds must pass; PASS -> ASK_LATER only.")
    K.report("b84_combined_copula_stretch", L)


if __name__ == "__main__":
    main()
