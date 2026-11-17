"""22.V1 (New_Plan 22.2): whole-profile balloon templates for the shuffle, climate mode, in memory only (assets untouched). REPORT ONLY.
What: for each case (station, calendar month, UTC hour) the rank templates `post["rank"]` of that month (all 12 two-hour bins, all blocks) are replaced by ranks of 199 COMPLETE real balloon
profiles (u, v, T, all 44 heights each, same station / month / hour, 1991-2020; one profile = one template row, so all heights and variables of a member come from the SAME balloon).
The other columns (surface and RH columns) keep the shipped ranks; they are not scored here. rank_extra (further template draws) is dropped in the patched run so every block uses the balloon set.
If fewer than 199 complete balloons exist the set is drawn with repeats and the share is logged. Values per height stay the tool's calibrated marginals (CRPS equal by construction).
Arms: shipped (control, same cases and seeds), V1a (balloon templates, shear and lapse maps ON), V1b (balloon templates, shear and lapse maps OFF); gaussfull one member per case (b9 stand-in) as the reference bar.
Cases: b9 list (EPZ / MAF, 00Z / 12Z, 2024-25, 200 per group), 50 members per case, one random member for the correlation error (as b9 / b70).
PRE-SET RULE (before the run; from New_Plan 22.2 V1 'Pass' and 'Kill'):
  PASS (per arm): vertical-corr error <= 0.045 AND the day-bootstrap interval of (arm - gaussfull) includes 0 or sits below 0 (lower end <= 0)
                  AND CRPS u, v, T not worse than shipped by more than 0.3 % (lower = better is fine; clarified 2026-11-17 before the full run, after a 16-case smoke showed the maps interacting with the new order) AND shear p99 ratio and Ri<1 share in the 12-18 km band not worse than shipped (p99 ratio within 0.05 of 1 or closer to 1 than shipped; Ri<1 share closer to the balloons than shipped or within 0.01).
  KILL: all arms above 0.050 vertical-corr error.   Otherwise MISS (report which limit failed).
  Error noise: single errors carry sampling noise (about 0.03 at 600 cases); shipped and arms share the cases, so differences are read from the paired day-bootstrap of (arm - shipped), also printed.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b71_v1_balloon_templates.py      # KIT_SMOKE=1 ... --per-group 4 for a test
Result: docs/results/logs/kit_b71_v1_balloon_templates.log
"""
import argparse

import numpy as np
import pandas as pd

import kit_common as K
import b9_gram_compare as B9
from b1_shape_scores import ri_counts

VARS = ("u", "v", "T")
NM = 50
NT = 199
ARMS = ("shipped", "V1a maps on", "V1b maps off")
_TPL = {}


def balloon_ranks(sid, month, hour, rng):
    """(199, 3*44) rank template (uint8) from complete balloon profiles; returns (ranks, n complete, repeats used)."""
    key = (sid, month, hour)
    if key not in _TPL:
        c = B9.clim(sid, month, hour)
        x = np.hstack([c["u"], c["v"], c["T"]])
        ok = np.flatnonzero(np.isfinite(x).all(1))
        assert len(ok) >= 30, f"{key}: only {len(ok)} complete balloons"
        rep = len(ok) < NT
        sel = rng.choice(ok, NT, replace=rep)
        r = np.argsort(np.argsort(x[sel], axis=0, kind="stable"), axis=0, kind="stable").astype(np.uint8)
        _TPL[key] = (r, len(ok), rep)
    return _TPL[key]


def run_arm(api, A, arm, month, ranks, lat, lon, t, elev, seed):
    full = A["post"]
    if arm == "shipped":
        return K.tool(lat, lon, t, seed=seed, n=NM, elevation=elev)
    post = {k: v for k, v in full.items() if k != "rank_extra" and not (arm == "V1b maps off" and k in ("smap", "lmap"))}
    sl = slice(month * 12, month * 12 + 12)
    saved = full["rank"][:, sl, :, :3 * K.NH].copy()
    full["rank"][:, sl, :, :3 * K.NH] = ranks[None, None]
    A["post"] = post
    try:
        return K.tool(lat, lon, t, seed=seed, n=NM, elevation=elev)
    finally:
        A["post"] = full
        full["rank"][:, sl, :, :3 * K.NH] = saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=200)
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    from tempest_weather import api
    A = api._assets()
    rng = np.random.default_rng(0)
    todo = B9.cases(a.per_group, rng)
    srcs = list(ARMS) + ["gaussfull"]
    pick = {s: {q: [] for q in VARS} for s in srcs + ["balloons"]}
    crps = {s: {q: [] for q in VARS} for s in srcs}
    shear = {s: [] for s in srcs + ["balloons"]}
    ri = {s: np.zeros((4, 2)) for s in srcs + ["balloons"]}
    days, skipped, repeats = [], 0, set()
    trng = np.random.default_rng(5)
    for cid, sid, t, b in todo:
        lat, lon, elev = K.station_pos(sid)
        mu, _ = B9.clim_stats(sid, t.month, t.hour)
        seed = 1000 * t.year + int(t.dayofyear)
        try:
            ranks, nok, rep = balloon_ranks(sid, t.month, t.hour, trng)
            runs = {arm: run_arm(api, A, arm, t.month - 1, ranks, lat, lon, t, elev, seed) for arm in ARMS}
        except ValueError:
            skipped += 1
            continue
        if rep:
            repeats.add((sid, t.month, t.hour, nok))
        gm = B9.gauss_members(sid, t.month, t.hour, NM, rng)
        mem = {s: {q: np.asarray(runs[s][q], float) for q in (*VARS, "p")} for s in ARMS}
        mem["gaussfull"] = gm
        days.append(f"{t:%Y-%m-%d}")
        for q in VARS:
            pick["balloons"][q].append(b[q] - mu[q])
        shear["balloons"].append(K.shear_mag(b["u"], b["v"])[None])
        ri["balloons"] += ri_counts(b["u"], b["v"], b["T"], b["p"])
        for s in srcs:
            x = mem[s]
            j = int(rng.integers(NM))
            for q in VARS:
                pick[s][q].append(x[q][j] - mu[q])
                crps[s][q].append(np.nanmean(B9.crps_cols(x[q], b[q])))
            shear[s].append(K.shear_mag(x["u"], x["v"]))
            ri[s] += ri_counts(x["u"], x["v"], x["T"], x["p"])
    n = len(days)
    assert n >= 8, f"only {n} cases"
    days = np.array(days)
    pick = {s: {q: np.array(v) for q, v in d.items()} for s, d in pick.items()}
    err = lambda s, i: B9.vert_err({q: pick[s][q][i] for q in VARS}, {q: pick["balloons"][q][i] for q in VARS})
    every = np.arange(n)
    L = [f"22.V1 balloon templates: {n} cases ({skipped} skipped), {NM} members, template sets with repeats (fewer than {NT} complete balloons): {len(repeats)} of the station / month / hour groups used",
         "source                vertical-corr error     CRPS u    v     T     shear p99 ratio per band        Ri<1 share per band"]
    sb = np.concatenate(shear["balloons"])
    r99 = {}
    for s in srcs:
        sh = np.concatenate(shear[s])
        with np.errstate(all="ignore"):
            r99[s] = [np.nanpercentile(sh[:, i], 99) / np.nanpercentile(sb[:, i], 99) for i in B9.MIDB]
        L.append(f"  {s:<20} {err(s, every):<22.3f} " + " ".join(f"{np.mean(crps[s][q]):<6.3f}" for q in VARS) + "  " + " ".join(f"{x:.2f}" for x in r99[s]) + "      "
                 + " ".join(f"{x:.3f}" for x in ri[s][:, 0] / np.maximum(ri[s][:, 1], 1)))
    L.append("  balloons             -                      -                       1.00 1.00 1.00 1.00             " + " ".join(f"{x:.3f}" for x in ri["balloons"][:, 0] / np.maximum(ri["balloons"][:, 1], 1)))
    verdict = {}
    for arm in ARMS[1:]:
        d_ship = B9.boot(lambda i, arm=arm: err(arm, i) - err("shipped", i), days, a.boot)
        d_gf = B9.boot(lambda i, arm=arm: err(arm, i) - err("gaussfull", i), days, a.boot)
        cr = {q: 100 * (np.mean(crps[arm][q]) / np.mean(crps["shipped"][q]) - 1) for q in VARS}
        e = err(arm, every)
        rs = ri[arm][3, 0] / max(ri[arm][3, 1], 1)
        rb = ri["balloons"][3, 0] / max(ri["balloons"][3, 1], 1)
        rsh = ri["shipped"][3, 0] / max(ri["shipped"][3, 1], 1)
        ok = {"error <= 0.045": e <= 0.045, "vs gaussfull includes 0 or below": d_gf[1] <= 0,
              "CRPS not worse than shipped by over 0.3 %": all(v <= 0.3 for v in cr.values()),
              "p99 12-18 km not worse": abs(r99[arm][3] - 1) <= max(abs(r99["shipped"][3] - 1), 0.05),
              "Ri<1 12-18 km not worse": abs(rs - rb) <= max(abs(rsh - rb), 0.01)}
        verdict[arm] = ok
        L.append(f"{arm}: error {e:.3f}; vs shipped {d_ship[0]:+.4f} [{d_ship[1]:+.4f}, {d_ship[2]:+.4f}]; vs gaussfull {d_gf[0]:+.4f} [{d_gf[1]:+.4f}, {d_gf[2]:+.4f}]; CRPS vs shipped "
                 + " ".join(f"{q} {v:+.2f} %" for q, v in cr.items()) + "; limits: " + "; ".join(f"{k} {'ok' if v else 'FAIL'}" for k, v in ok.items()))
    errs = [err(arm, every) for arm in ARMS[1:]]
    word = "KILL" if all(x > 0.050 for x in errs) else ("PASS " + ", ".join(k for k, v in verdict.items() if all(v.values()))) if any(all(v.values()) for v in verdict.values()) else "MISS"
    L.append(f"VERDICT (pre-set rule): {word}")
    L.append("Notes: development window (2024-25), EPZ / MAF; the tool is balloon-corrected here and the templates come from the same station's 1991-2020 balloons, so this is not a blind test. "
             "Sites without balloons (k-nearest stations) and the 2026 window are not run here. The 90 % interval reads the day-bootstrap 2.5-97.5 band of B9.boot (a little wider).")
    K.report("b71_v1_balloon_templates", L)


if __name__ == "__main__":
    main()
