"""New_Plan 29.5 X1 (2026-11-19): marginal-locked W2 copula + T-roughness damping. No stretch.
Arms on the same cases as b84 (b9 list: EPZ / MAF, 00Z / 12Z, 2024-25, --per-group cases per group, default 450 = 1800; 50 members):
  shipped   tool as shipped (control)
  locked    W2 copula arm (u,v ranks from balloons, maps on), then per column (u, v, T) the shipped post-map values are put back by rank: the member with
            the k-th smallest copula value gets the k-th smallest shipped value, so the per-height marginals (and CRPS) equal shipped, only the dependence is the copula's
  locked+T  locked, then the fine-scale part of T (T minus a 9-height uniform window, as W1) is scaled by g per band, g = sqrt(balloon / member rough variance)
            fit on the EVEN cases, clipped to 0.5-1 (damping only); verdict arm. Tested on the ODD cases.
PRE-SET RULE (written before any run; both seeds KIT_SEED 0 and 1 needed; point estimates, no interval clause: 26.1 showed the interval width does not shrink with cases):
  (a) vertical-corr error of locked+T <= shipped error - 0.005,
  (b) CRPS u, v, T not worse than shipped by over 0.1 %,
  (c) shear p99 ratio 5-12 km >= 0.90,
  (d) Ri<1 share at 5-12 km and 12-18 km each within 0.03 of the balloons.
Else MISS and close. PASS -> ASK_LATER only, never shipped. Information also printed: locked alone, and the pooled-seed reading is left to the user.
    PYTHONPATH=".;new_plan_kit" KIT_SEED=0 .venv/Scripts/python -W ignore new_plan_kit/b86_x1_locked_copula.py [--per-group 450]   Result: docs/results/logs/kit_b86_x1_locked_copula.log
"""
import argparse
import os

import numpy as np
from scipy.ndimage import uniform_filter1d

import kit_common as K
import b9_gram_compare as B9
import b79_w2_copula_uv as W2
import b81_w1_shear_stretch as W
from b1_shape_scores import ri_counts

NM = 50
VARS = B9.VARS
LOCK = ("u", "v", "T")


def lock(cop, ship):
    """cop, ship: dicts of (NM, 44). Per column, shipped sorted values placed by the copula's ranks. Copy."""
    y = dict(cop)
    for q in LOCK:
        r = np.argsort(np.argsort(cop[q], axis=0, kind="stable"), axis=0, kind="stable")
        y[q] = np.take_along_axis(np.sort(ship[q], axis=0), r, axis=0)
    return y


def rough(x):
    return x - uniform_filter1d(x, 9, axis=-1, mode="nearest")


def damp(x, g):
    """x dict; g (4,) factors by band; T rough part scaled by g[band of level]. Copy; level 0 (surface) unchanged as in W1."""
    y = dict(x)
    sm = uniform_filter1d(x["T"], 9, axis=-1, mode="nearest")
    z = sm + g[W.LVL_BAND] * (x["T"] - sm)
    z[..., 0] = x["T"][..., 0]
    y["T"] = z
    return y


def fit_g(ship_T, bal_T):
    """ship_T: list of (NM, 44) fit-case member T; bal_T: list of (44,) balloon T. g per band = sqrt(balloon / member rough variance), in 0.5-1."""
    mr = np.concatenate([rough(x) for x in ship_T])               # (cases*NM, 44)
    br = np.stack([rough(b) for b in bal_T])                       # (cases, 44)
    g = np.ones(4)
    for b in range(4):
        k = W.LVL_BAND == b
        k[0] = False
        g[b] = np.clip(np.sqrt(np.nanvar(br[:, k]) / np.nanvar(mr[:, k])), 0.5, 1.0)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=450)
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
        ship = {q: np.asarray(ship[q], float) for q in (*VARS, "p")}
        cop = {q: np.asarray(cop[q], float) for q in (*VARS, "p")}
        C.append((f"{t:%Y-%m-%d}", mu, b, ship, lock(cop, ship)))
    n = len(C)
    assert n >= 8, f"only {n} cases"
    fit = [i for i in range(n) if i % 2 == 0]
    te = [i for i in range(n) if i % 2 == 1]
    nt = len(te)
    g = fit_g([C[i][3]["T"] for i in fit], [C[i][2]["T"] for i in fit])
    S = {"shipped": [C[i][3] for i in te], "locked": [C[i][4] for i in te], "locked+T": [damp(C[i][4], g) for i in te]}
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
        bb = C[i][2]
        cb += ri_counts(bb["u"], bb["v"], bb["T"], bb["p"])
    rib = cb[:, 0] / np.maximum(cb[:, 1], 1)
    every = np.arange(nt)
    err = {s: B9.vert_err({q: pick[s][q] for q in VARS}, {q: bal[q] for q in VARS}) for s in S}
    L = [f"X1 marginal-locked copula + T-roughness damping (seed {seed}): {n} cases ({skipped} skipped), fit {len(fit)}, test {nt}, {NM} members; T damping g per band " + " ".join(f"{x:.2f}" for x in g),
         "source      vertical-corr err   CRPS u v T            shear p99 ratio per band   Ri<1 per band"]
    for s in S:
        L.append(f"  {s:<10} {err[s]:<8.3f} " + " ".join(f"{crps[s][q]:<6.3f}" for q in VARS) + "  " + " ".join(f"{x:.2f}" for x in r99[s]) + "   " + " ".join(f"{x:.3f}" for x in ri[s]))
    L.append("  balloons ri " + " ".join(f"{x:.3f}" for x in rib))
    k = "locked+T"
    cr = {q: 100 * (crps[k][q] / crps["shipped"][q] - 1) for q in VARS}
    ok = {"err <= shipped - 0.005": err[k] <= err["shipped"] - 0.005,
          "CRPS u v T <= +0.1 %": all(v <= 0.1 for v in cr.values()),
          "p99 5-12 km >= 0.90": r99[k][2] >= 0.90,
          "Ri<1 5-12 and 12-18 km within 0.03": abs(ri[k][2] - rib[2]) <= 0.03 and abs(ri[k][3] - rib[3]) <= 0.03}
    L.append(f"{k}: err vs shipped {err[k] - err['shipped']:+.4f} (locked alone {err['locked'] - err['shipped']:+.4f}); CRPS " + " ".join(f"{q} {v:+.2f} %" for q, v in cr.items())
             + "; " + "; ".join(f"{x} {'ok' if v else 'FAIL'}" for x, v in ok.items()))
    L.append("VERDICT (pre-set rule, this seed): " + ("PASS" if all(ok.values()) else "MISS"))
    L.append("Notes: development window (2024-25), tool balloon-corrected, templates from the same station's balloons: not a blind test. Both seeds must pass; PASS -> ASK_LATER only.")
    K.report("b86_x1_locked_copula", L)


def _selfcheck():
    rng = np.random.default_rng(0)
    ship = {q: rng.normal(size=(NM, 44)) for q in ("u", "v", "T", "p")}
    cop = {q: rng.normal(size=(NM, 44)) * 2 + 1 for q in ("u", "v", "T", "p")}
    y = lock(cop, ship)
    for q in LOCK:                                                  # marginals equal shipped, ranks equal the copula's
        assert np.array_equal(np.sort(y[q], 0), np.sort(ship[q], 0))
        assert np.array_equal(np.argsort(y[q], 0), np.argsort(cop[q], 0))
    assert y["p"] is cop["p"]
    d = damp(ship, np.array([0.5, 0.5, 0.5, 0.5]))
    assert np.allclose(d["T"][:, 0], ship["T"][:, 0]) and rough(d["T"])[:, 5:-5].std() < rough(ship["T"])[:, 5:-5].std()
    g = fit_g([ship["T"]] * 3, [ship["T"][0] * 0.5] * 3)
    assert ((g >= 0.5) & (g <= 1)).all() and g.max() < 1


_selfcheck()
if __name__ == "__main__":
    main()
