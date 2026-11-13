"""Block 1 one-hour checks. One sub-command each; every one prints a VERDICT line that says what to do next.

  trend    G1-7: does the shipped network have a trend input (year or gmst)? If yes, the drift tracker only needs the replay.
  il128    IL-128 on a REAL pool: does the engine's copula sampling (sample_sobol) inflate extreme shear? Spaceport, 4 dates, pool of 4000.
           ratio = p99.9 shear of 20000 copula samples / p99.9 shear of the pool, per layer band.
           Any ratio above 1.2 -> G3-3 (select, then nudge) becomes a candidate (New_Plan.md section 7). All at or under 1.2 -> close IL-128.
  oracle   G1-4: how much could better shuffle templates gain at most? For each test row the template = the 199 real training profiles of its
           group NEAREST to the true profile (an oracle: it uses the answer). Variogram score (lower = better joint shape) against today's templates.
           Gain under 1 % -> close G1-4 and G3-4. Gain of 1 % or more -> the template choice matters; keep G1-4 open and report.
  (G2-1, the spectrum of detail between heights, is NOT POSSIBLE from disk: data/igra_heights holds only the 44 model heights. It needs
   1-second soundings, a download that was not asked for. Skip it.)

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_quick_checks.py trend            # seconds
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_quick_checks.py il128            # 2-3 min, 2 GB RAM
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_quick_checks.py oracle --device cpu    # about 15 min, 5 GB RAM
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_quick_checks.py oracle --device cpu --rows 20   # smoke test
Result: docs/results/logs/kit_b1_quick_<name>.log
"""
import argparse
import os

import numpy as np

import kit_common as K

SPACEPORT = (32.99, -106.97, 1401.0)


def trend(a):
    import torch
    from b1_build_pool import MODEL
    from tempest.generator.sample import Sampler
    names = Sampler(torch.load(os.path.join(K.REPO, MODEL + ".pt"), map_location="cpu", weights_only=True), device="cpu").cond_names
    if names is None:
        from tempest.generator.features import BASE_FEATURES as names
    has = [k for k in ("year", "gmst") if k in names]
    K.report("b1_quick_trend", [f"G1-7 trend-input check: the shipped network ({MODEL}) takes these inputs: {', '.join(names)}",
                                f"VERDICT: trend input present ({', '.join(has)}). G1-7 only needs the replay (recipe: new_plan_kit/README.md, item G1-7)." if has else
                                "VERDICT: NO trend input. G1-7 drift tracker is needed in full (recipe: new_plan_kit/README.md, item G1-7)."])


def shear_ratio(pool, big):
    """p99.9 neighbour-height shear of the copula samples over the pool's, per layer band -> list of (name, pool, sample, ratio)."""
    out = []
    sp, sg = K.shear_mag(np.asarray(pool["u"]), np.asarray(pool["v"])), K.shear_mag(np.asarray(big["u"]), np.asarray(big["v"]))
    for lo, hi in ((10, 500), (500, 2000), (2000, 6000), (6000, 18000)):
        m = (K.H[1:] >= lo) & (K.H[1:] < hi)
        p, s = np.quantile(sp[:, m], 0.999), np.quantile(sg[:, m], 0.999)
        out.append((f"{lo}-{hi} m", p, s, s / p))
    return out


def il128(a):
    from tempest_weather.flight import TempestFlightSimEngine
    lat, lon, elev = SPACEPORT
    lines, worst = ["IL-128 on real pools (Spaceport, pool 4000, 20000 copula samples): p99.9 shear, m/s per km", "date              layer band      pool    sample   ratio"], 0.0
    for t in ("2024-01-15T18:00", "2024-04-15T21:00", "2025-07-15T15:00", "2025-10-15T00:00"):
        atm = K.tool(lat, lon, t, seed=0, n=a.n, elevation=elev)
        pool = {k: np.asarray(atm[k]) for k in ("u", "v", "T", "RH", "t2m", "sp", "rh2m")}
        big = TempestFlightSimEngine(atm=pool, info={"elevation_m": elev}).sample_sobol(np.random.default_rng(1).random((20000, 6)))
        for name, p, s, r in shear_ratio(pool, big):
            lines.append(f"{t:<18}{name:<16}{p:<8.2f}{s:<9.2f}{r:.2f}")
            worst = max(worst, r)
    lines.append(f"VERDICT: worst ratio {worst:.2f} > 1.2: the copula sampling inflates extreme shear. G3-3 becomes a candidate (New_Plan.md section 7)." if worst > 1.2 else
                 f"VERDICT: worst ratio {worst:.2f}, at or under 1.2: no inflation on real pools. Close IL-128; G3-3 stays unbuilt. (Ratios under 0.85 mean the copula sampling LOSES extreme shear: report that number, build nothing.)")
    K.report("b1_quick_il128", lines)


def nearest_templates(d, keys, idx, truth, m, sd, before_year, cap=4000, seed=0):
    """Per row: the m training-year profiles of its group (8 x 8 block x month x hour bin) nearest to the truth (RMS over columns / sd) -> (len(idx), m, D)."""
    from tempest.calibrate import shuffle
    from tempest.generator.sample import to_physical
    rng = np.random.default_rng(seed)
    ck = shuffle.cell_keys(keys, 8, shuffle.grid_n_lon(d["cond"]))
    tr = np.flatnonzero(np.asarray(d["year"]) < before_year)
    tr = tr[np.argsort(ck[tr], kind="stable")]
    lo, hi = np.searchsorted(ck[tr], ck[idx], "left"), np.searchsorted(ck[tr], ck[idx], "right")
    out = np.empty((len(idx), m, truth.shape[1]), np.float32)
    for i in range(len(idx)):
        n = hi[i] - lo[i]
        g = to_physical(np.asarray(d["target"][np.sort(tr[lo[i] + rng.choice(n, min(cap, n), replace=False)])]))
        out[i] = g[np.argsort((((g - truth[i]) / sd) ** 2).sum(1))[:m]]
    return out


def oracle(a):
    from b1_build_pool import stages
    from tempest.calibrate import shuffle
    from tempest.scoring.score import variogram_score
    K.ram_gate(8.0)
    s = stages(rows=a.rows, device=a.device)
    sd = s["truth"].std(0) + 1e-9
    xo = shuffle.apply(s["x_cal"], nearest_templates(s["d"], s["keys"], s["idx"], s["truth"], 199, sd, 2024))
    lines, gains = [f"G1-4 oracle templates: {len(s['idx'])} rows of 2024-25, 199 members, shuffle only (no maps), variogram score per variable (columns / sd)",
                    "variable   today's templates   oracle templates   gain"], []
    for j, name in enumerate(("u", "v", "T")):
        c = slice(j * K.NH, (j + 1) * K.NH)
        v0, v1 = (variogram_score(x[..., c] / sd[c], s["truth"][:, c] / sd[c], chunk=50).mean() for x in (s["x_shuf"], xo))
        gains.append(1 - v1 / v0)
        lines.append(f"{name:<11}{v0:<20.4f}{v1:<19.4f}{gains[-1]:+.1%}")
    g = float(np.mean(gains))
    lines.append(f"VERDICT: mean gain {g:+.1%}, under 1 %: even perfect templates do not help. Close G1-4 and G3-4." if g < 0.01 else
                 f"VERDICT: mean gain {g:+.1%}, 1 % or more with ORACLE templates (an upper limit, not reachable in use). Keep G1-4 open and report; build nothing yet.")
    K.report("b1_quick_oracle", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    u = rng.standard_normal((500, K.NH))
    r = shear_ratio(dict(u=u, v=u), dict(u=2 * u, v=2 * u))
    assert len(r) == 4 and all(abs(x[3] - 2.0) < 1e-9 for x in r)


_selfcheck()
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("check", choices=["trend", "il128", "oracle"])
    ap.add_argument("--rows", type=int, default=600)
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--device")
    a = ap.parse_args()
    {"trend": trend, "il128": il128, "oracle": oracle}[a.check](a)
