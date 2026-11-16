"""New_Plan 12.3 VS stage 1: the library bar. Each member of the shipped stack with the shear and lapse maps OFF (stage "+ shuffle") keeps its coarse view (13 of the 44 heights, linear in height between them);
the fine layers between are replaced by one whole real leftover (a balloon minus its own coarse view) drawn from the same station, calendar month, UTC hour (1991-2020, complete balloons) and
the same stability third (T at about 3 km minus T at 10 m, thirds of that library). Values at the 13 coarse heights are those of the member (u, v, T); p is rebuilt hydrostatically from the member's surface p.
Cases: EPZ and MAF balloons, 00Z / 12Z, 2024-25 (the b9 development window, never 2026). Stated limits: the plan text says left-out stations and 2022; here the two stations the tool is scored at and 2024-25 (as b9 / E5),
and the library holds the same station, no left-out stations. One seed, --per-group cases per station x hour.
Scores per source (tool shipped, tool + shuffle, bar), per case then pooled: Ri < 1 share per band (b1 ri_counts), mean count per profile of T rises > 2 K below 3 km (b1 inversions),
shear p99 ratio to balloons per band (all members x layers against the balloon layers), CRPS of u, v, T (mean of the four band means, as b9).
Rule (set 2026-11-16 before running; New_Plan 12.3 stage 1): the bar PASSES stage 1 if ALL hold: (1) Ri < 1 share within 0.03 of the balloons in every band; (2) T-rise count within 0.05 of the balloons;
(3) shear p99 within 10 % of the balloons (ratio 0.90-1.10) in every band; (4) CRPS of u, v and T not worse than the shipped stack by more than kit_common.PAIRED_TOL (0.0009).
Otherwise MISS (the bar is only the reference for VS stage 2; nothing ships on this). Report every number.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b65_vs_library_bar.py [--per-group 100] [--m 100]
Result: docs/results/logs/kit_b65_vs_library_bar.log
"""
import argparse

import numpy as np

import b1_shape_scores as B1
import b9_gram_compare as B9
import kit_common as K

NAME = "b65_vs_library_bar"
VARS = ("u", "v", "T")
CI = np.unique(np.round(np.linspace(0, K.NH - 1, 13)).astype(int))
W = np.stack([np.interp(K.H, K.H[CI], np.eye(len(CI))[i]) for i in range(len(CI))], 1)     # (44, 13): coarse values -> all heights
I3 = int(np.argmin(np.abs(K.H - 3000.0)))
RD, G = 287.05, 9.80665


def coarse_view(x):
    return x[..., CI] @ W.T


def stab(T):
    return T[..., I3] - T[..., 0]


def library(sid, month, hour):
    """complete 1991-2020 balloons of one station / month / hour -> leftovers dict (n, 44) and stability (n,)."""
    c = B9.clim(sid, month, hour)
    ok = np.flatnonzero(np.isfinite(np.hstack([c["u"], c["v"], c["T"], c["lnp"]])).all(1))
    return {q: c[q][ok] - coarse_view(c[q][ok]) for q in VARS}, stab(c["T"][ok])


def bar_members(mem, lib, st, rng):
    """mem: dict u, v, T, p (m, 44) -> same dict with the fine layers of a real leftover of the member's stability third."""
    cuts = np.quantile(st, [1 / 3, 2 / 3])
    third_lib = np.digitize(st, cuts)
    third_mem = np.digitize(stab(mem["T"]), cuts)
    out = {q: coarse_view(mem[q]).copy() for q in VARS}
    for k in range(len(mem["u"])):
        pool = np.flatnonzero(third_lib == third_mem[k])
        j = rng.choice(pool)
        for q in VARS:
            out[q][k] += lib[0][q][j]
    for q in VARS:
        out[q][:, CI] = mem[q][:, CI]
    tbar = 0.5 * (out["T"][:, 1:] + out["T"][:, :-1])
    lnp = np.log(mem["p"][:, :1]) + np.hstack([np.zeros((len(tbar), 1)), np.cumsum(-G * np.diff(K.H) / (RD * tbar), 1)])
    out["p"] = np.exp(lnp)
    return out


class Acc:
    def __init__(self):
        self.ri, self.inv, self.n, self.sh = np.zeros((4, 2)), 0.0, 0, [[] for _ in range(4)]
        self.crps = {q: [] for q in VARS}

    def add(self, x, b=None):
        self.ri += B1.ri_counts(x["u"], x["v"], x["T"], x["p"])
        self.inv += float(np.mean(B1.inversions(x["T"])))
        self.n += 1
        s = K.shear_mag(x["u"], x["v"])
        for i, m in enumerate(B1.BMASK):
            self.sh[i].append(s[..., m].ravel())
        if b is not None:
            for q in VARS:
                c = B9.crps_cols(x[q], b[q])
                self.crps[q].append(float(np.nanmean([np.nanmean(c[i]) for i in B9.BIDX])))

    def summary(self):
        ri = self.ri[:, 0] / np.maximum(self.ri[:, 1], 1)
        p99 = [float(np.nanpercentile(np.concatenate(s), 99)) for s in self.sh]
        return ri, self.inv / max(self.n, 1), np.array(p99), {q: float(np.mean(v)) for q, v in self.crps.items() if v}


def judge(bal, bar, ship):
    """(Ri, inv, p99, crps) of balloons, bar, shipped -> (verdict, list of failed limits)."""
    fail = []
    if np.abs(bar[0] - bal[0]).max() > 0.03:
        fail.append("Ri<1 share")
    if abs(bar[1] - bal[1]) > 0.05:
        fail.append("T-rise count")
    r = bar[2] / bal[2]
    if (r < 0.90).any() or (r > 1.10).any():
        fail.append("shear p99")
    if any(bar[3][q] - ship[3][q] > K.PAIRED_TOL for q in VARS):
        fail.append("CRPS")
    return ("PASS" if not fail else "MISS"), fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=100)
    ap.add_argument("--m", type=int, default=100)
    a = ap.parse_args()
    K.ram_gate(3.0)
    rng = np.random.default_rng(0)
    todo = B9.cases(a.per_group, rng)
    accs = {s: Acc() for s in ("balloons", "shipped", "+ shuffle", "bar")}
    libs, skipped = {}, 0
    for cid, sid, t, b in todo:
        lat, lon, elev = K.station_pos(sid)
        seed = 1000 * t.year + int(t.dayofyear)
        try:
            ship = K.tool(lat, lon, t, seed=seed, n=a.m, elevation=elev)
            shuf = K.tool(lat, lon, t, seed=seed, n=a.m, elevation=elev, stage="+ shuffle")
        except ValueError:
            skipped += 1
            continue
        key = (sid, t.month, t.hour)
        if key not in libs:
            libs[key] = library(*key)
        lib, st = libs[key]
        sh = {q: np.asarray(shuf[q], float) for q in (*VARS, "p")}
        bar = bar_members(sh, (lib, st), st, rng)
        accs["balloons"].add({q: b[q][None] for q in (*VARS,)} | {"p": b["p"][None]})
        accs["shipped"].add({q: np.asarray(ship[q], float) for q in (*VARS, "p")}, b)
        accs["+ shuffle"].add(sh, b)
        accs["bar"].add(bar, b)
    n = accs["balloons"].n
    S = {k: v.summary() for k, v in accs.items()}
    lines = [f"VS stage 1 library bar: {n} cases (EPZ / MAF 00Z 12Z 2024-25), {a.m} members, {skipped} skipped; coarse heights {len(CI)} of {K.NH}",
             "  Ri<1 share per band (0-1, 1-5, 5-12, 12-18 km), T-rise count < 3 km, shear p99 (m/s per km) per band, CRPS u / v / T:"]
    for k in ("balloons", "shipped", "+ shuffle", "bar"):
        ri, inv, p99, cr = S[k]
        lines.append(f"  {k:10s} Ri {', '.join(f'{x:.3f}' for x in ri)} | rise {inv:.3f} | p99 {', '.join(f'{x:.1f}' for x in p99)} | " + (" ".join(f'{q} {cr[q]:.4f}' for q in VARS) if cr else "CRPS -"))
    lines.append("  bar minus balloons: Ri " + ", ".join(f"{x:+.3f}" for x in S['bar'][0] - S['balloons'][0]) + f" | rise {S['bar'][1] - S['balloons'][1]:+.3f} | p99 ratio " + ", ".join(f"{x:.2f}" for x in S['bar'][2] / S['balloons'][2]))
    lines.append("  bar minus shipped CRPS: " + " ".join(f"{q} {S['bar'][3][q] - S['shipped'][3][q]:+.4f}" for q in VARS) + f" (tolerance {K.PAIRED_TOL})")
    v, fail = judge(S["balloons"], S["bar"], S["shipped"])
    lines.append("Rule (pre-set): PASS = Ri<1 within 0.03 in every band, T-rise within 0.05, shear p99 ratio 0.90-1.10 in every band, CRPS u v T not worse than shipped by more than 0.0009; else MISS.")
    lines.append("Verdict: " + v + (f" (failed: {', '.join(fail)})" if fail else ""))
    K.report(NAME, lines)


def _selfcheck():
    assert np.allclose(coarse_view(K.H[None, :] * 2.0), K.H[None, :] * 2.0) and W.shape == (K.NH, len(CI))
    rng = np.random.default_rng(0)
    x = {"u": rng.normal(size=(5, K.NH)), "v": rng.normal(size=(5, K.NH)), "T": 280 - K.H[None, :] / 150 + rng.normal(size=(5, K.NH)), "p": 1e5 * np.exp(-K.H / 8000)[None, :] * np.ones((5, 1))}
    lib = ({q: rng.normal(size=(30, K.NH)) for q in VARS}, rng.normal(size=30))
    y = bar_members(x, lib, lib[1], rng)
    assert all(np.allclose(y[q][:, CI], x[q][:, CI]) for q in VARS) and np.allclose(y["p"][:, 0], x["p"][:, 0])
    bal = (np.array([.7, .3, .2, .1]), 0.3, np.array([10, 10, 10, 10.]), {})
    ok = (np.array([.7, .3, .2, .1]), 0.3, np.array([10, 10, 10, 10.]), {"u": 1., "v": 1., "T": 1.})
    assert judge(bal, ok, ok)[0] == "PASS" and judge(bal, (ok[0] + .1,) + ok[1:], ok)[0] == "MISS"


_selfcheck()
if __name__ == "__main__":
    main()
