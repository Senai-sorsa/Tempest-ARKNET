"""New_Plan 12.3 VS stage 2: a learned fine-scale model against the library bar (b65).
VS = nearest-neighbour conditional leftover (a non-parametric stand-in for the planned net, CPU, no GPU needed): each member of the shipped stack with the shear and lapse maps OFF keeps its
13-height coarse view (b65); the fine layers are replaced by the leftover (balloon minus its own coarse view) of one of the K nearest training balloons in the space of
[coarse u, v, T of the member (each standardised by the training sd), sin / cos of the month, |lat|/90 (weight 3 each)]. Training = complete balloons 1991-2020 of all stations except
those held out (EPZ, MAF, Denver 72469, plus crc32(station id) % 5 == 0), at most 150 random balloons per station. K is chosen on 2021 (K in 20, 100, 400, lowest mean vertical variogram score), then TEST = 2022 balloons at EPZ, MAF and Denver (the only places the tool runs: its assets cover lat 31-34 / lon -108..-101 and Denver; so the planned 'left-out stations' are these 3).
Bar = b65 (same-station library of the member's calendar month / UTC hour / stability third, 1991-2020). Baseline = shipped stack. Cases: 3 test stations, up to 40 complete 2022 balloons per UTC hour each, the tool run at that station's position and elevation, 100 members. Two seeds (case choice and member draws). Stated limits: kNN not a trained net; 2022 only; the bar's library holds the
same station (an advantage over VS, which has never seen the station); only 3 test stations.
Scores: VARIOGRAM = mean over u, v, T of B9.vs_profile (p 0.5) per case; paired difference VS - bar with a 95 % day-block interval (kit_common.block_boot); b65 limits for VS (Ri<1 per band within 0.03 of balloons,
T-rise within 0.05, shear p99 ratio 0.90-1.10 per band, CRPS u v T not worse than shipped by more than 0.0009).
Rule (set 2026-11-16 before running): PASS = in BOTH seeds the VS - bar interval is below 0 AND VS meets all four limits (b65 judge). KILL = in NEITHER seed is VS better than the bar (interval not below 0):
the bar ships as the opt-in and VS is closed. Otherwise MISS. Report every number.
    source scripts/cap_cpu.sh; PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore -u new_plan_kit/b69_vs_stage2.py [--seeds 0 1] [--per-hour 3] [--m 100]
Result: docs/results/logs/kit_b69_vs_stage2.log
"""
import argparse
import glob
import os
import zlib

import numpy as np
import pandas as pd

import b9_gram_compare as B9
import b65_vs_library_bar as B65
import kit_common as K

NAME = "b69_vs_stage2"
VARS = ("u", "v", "T")
PER_STN = 150
KS = (20, 100, 400)


TEST_ST = (K.EPZ, K.MAF, "USM00072469")      # the tool is trained only for lat 31-34 / lon -108..-101 and Denver, so these are the only stations it can run at


def held(sid):
    return sid in TEST_ST or zlib.crc32(sid.encode()) % 5 == 0


def station_data(sid):
    """-> times, dict u, v, T, p (n, 44), complete rows only."""
    t, b = K.balloon(sid)
    ok = np.isfinite(np.hstack([b["u"], b["v"], b["T"], b["p"]])).all(1)
    return t[ok], {q: b[q][ok] for q in b}


def feats(x, month, lat):
    """x dict of u, v, T (n, 44) -> (n, 39 + 3) raw features."""
    c = [x[q][:, B65.CI] for q in VARS]
    n = len(c[0])
    return np.hstack(c + [np.full((n, 1), np.sin(2 * np.pi * month / 12)), np.full((n, 1), np.cos(2 * np.pi * month / 12)), np.full((n, 1), abs(lat) / 90.0)])


class Model:
    def __init__(self, F, L):
        self.mu, self.sd = F.mean(0), F.std(0) + 1e-6
        self.sd[-3:] = 1 / 3.0                               # weight of month / latitude terms
        self.mu[-3:] = 0.0
        self.F, self.L = ((F - self.mu) / self.sd).astype(np.float32), L

    def draw(self, f, k, rng):
        z = ((f - self.mu) / self.sd).astype(np.float32)
        d = (z ** 2).sum(1)[:, None] - 2 * z @ self.F.T + (self.F ** 2).sum(1)[None]
        nn = np.argpartition(d, k, axis=1)[:, :k]
        return self.L[nn[np.arange(len(z)), rng.integers(0, k, len(z))]]


def train(ids):
    F, L = [], []
    rng = np.random.default_rng(5)
    for s in ids:
        t, b = station_data(s)
        m = (t.year >= 1991) & (t.year <= 2020)
        idx = rng.permutation(np.flatnonzero(m))[:PER_STN]
        if len(idx) < 20:
            continue
        lat = float(np.load(os.path.join(K.REPO, "data/igra_heights", s + ".npz"))["lat"][-1])
        x = {q: b[q][idx] for q in VARS}
        for mo in np.unique(t.month[idx]):
            sel = t.month[idx] == mo
            xs = {q: x[q][sel] for q in VARS}
            F.append(feats(xs, mo, lat))
            L.append(np.hstack([xs[q] - B65.coarse_view(xs[q]) for q in VARS]))
    return np.vstack(F), np.vstack(L)


def vs_member(mod, mem, month, lat, k, rng):
    """b65-style member (shuffle stage) -> VS members: coarse view kept + kNN leftover, p rebuilt hydrostatically."""
    left = mod.draw(feats(mem, month, lat), k, rng)
    out = {q: B65.coarse_view(mem[q]) + left[:, i * K.NH:(i + 1) * K.NH] for i, q in enumerate(VARS)}
    for q in VARS:
        out[q][:, B65.CI] = mem[q][:, B65.CI]
    tbar = 0.5 * (out["T"][:, 1:] + out["T"][:, :-1])
    lnp = np.log(mem["p"][:, :1]) + np.hstack([np.zeros((len(tbar), 1)), np.cumsum(-B65.G * np.diff(K.H) / (B65.RD * tbar), 1)])
    out["p"] = np.exp(lnp)
    return out


def vscore(x, b):
    return float(np.mean([B9.vs_profile(x[q], b[q]) for q in VARS]))


def judge(better, meets):
    """better: list over seeds of 'interval below 0'; meets: list of 'VS meets all four limits'."""
    if all(better) and all(meets):
        return "PASS"
    if not any(better):
        return "KILL (VS is not better than the bar in either seed: the bar ships as the opt-in, VS closed)"
    return f"MISS (better than the bar in {sum(better)} of {len(better)} seeds; limits met in {sum(meets)} of {len(meets)})"


def cases_for(ids, year, per_hour, rng, limit):
    out = []
    for s in rng.permutation(ids):
        t, b = station_data(s)
        yr = t.year == year
        cs = []
        for h in (0, 12):
            idx = np.flatnonzero(yr & (t.hour == h))
            cs += [(s, t[i], {q: b[q][i] for q in b}) for i in rng.permutation(idx)[:per_hour]]
        if len(cs) >= 2 * per_hour:
            out += cs
        if len(set(c[0] for c in out)) >= limit:
            break
    return out


def run_cases(todo, m, rng, make):
    """-> per case dict of score rows; make(mem, month, lat) gives VS members. Returns accs and per-case lists."""
    accs = {k: B65.Acc() for k in ("balloons", "shipped", "bar", "vs")}
    vsb, vsv, days, skipped, libs = [], [], [], 0, {}
    for sid, t, b in todo:
        d = np.load(os.path.join(K.REPO, "data/igra_heights", sid + ".npz"))
        lat, lon, elev = float(d["lat"][-1]), float(d["lon"][-1]), float(d["elev"][-1])
        seed = 1000 * t.year + int(t.dayofyear)
        try:
            ship = K.tool(lat, lon, t, seed=seed, n=m, elevation=elev)
            shuf = K.tool(lat, lon, t, seed=seed, n=m, elevation=elev, stage="+ shuffle")
        except ValueError:
            skipped += 1
            continue
        key = (sid, t.month, t.hour)
        if key not in libs:
            libs[key] = B65.library(*key)
        lib, st = libs[key]
        if len(st) < 20:
            skipped += 1
            continue
        sh = {q: np.asarray(shuf[q], float) for q in (*VARS, "p")}
        bar = B65.bar_members(sh, (lib, st), st, rng)
        vs = make(sh, t.month, lat, rng)
        accs["balloons"].add({q: b[q][None] for q in (*VARS, "p")})
        accs["shipped"].add({q: np.asarray(ship[q], float) for q in (*VARS, "p")}, b)
        accs["bar"].add(bar, b)
        accs["vs"].add(vs, b)
        vsb.append(vscore(bar, b))
        vsv.append(vscore(vs, b))
        days.append(f"{sid}|{t:%Y-%m-%d}")
    return accs, np.array(vsb), np.array(vsv), days, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--per-hour", type=int, default=40)
    ap.add_argument("--m", type=int, default=100)
    ap.add_argument("--stations", type=int, default=3)
    a = ap.parse_args()
    K.ram_gate(3.0)
    ids = sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(K.REPO, "data/igra_heights/*.npz")))
    fit_ids = [s for s in ids if not held(s)]
    hold = [s for s in TEST_ST if s in ids]
    F, L = train(fit_ids)
    mod = Model(F, L)
    lines = [f"VS stage 2 (kNN stand-in): train {len(F)} balloons from {len(fit_ids)} stations (1991-2020); {len(hold)} test stations (never in the VS training set); coarse heights {len(B65.CI)} of {K.NH}"]
    rng = np.random.default_rng(100)
    chk = cases_for(hold, 2021, 12, rng, 3)
    sc = {}
    for k in KS:
        _, _, v, _, _ = run_cases(chk, a.m, np.random.default_rng(1), lambda mem, mo, la, r, k=k: vs_member(mod, mem, mo, la, k, r))
        sc[k] = float(np.mean(v))
    kbest = min(sc, key=sc.get)
    lines.append(f"  K chosen on 2021 ({len(chk)} cases): " + ", ".join(f"K={k} vario {v:.4f}" for k, v in sc.items()) + f" -> K = {kbest}")
    better, meets = [], []
    for sd in a.seeds:
        rng = np.random.default_rng(sd)
        todo = cases_for(hold, 2022, a.per_hour, rng, a.stations)
        accs, vb, vv, days, skipped = run_cases(todo, a.m, rng, lambda mem, mo, la, r: vs_member(mod, mem, mo, la, kbest, r))
        S = {k: v.summary() for k, v in accs.items()}
        lines.append(f"  seed {sd}: {accs['balloons'].n} cases at {len(set(d.split('|')[0] for d in days))} held-out stations (2022), {a.m} members, {skipped} skipped")
        for k in ("balloons", "shipped", "bar", "vs"):
            ri, inv, p99, cr = S[k]
            lines.append(f"    {k:9s} Ri {', '.join(f'{x:.3f}' for x in ri)} | rise {inv:.3f} | p99 {', '.join(f'{x:.1f}' for x in p99)} | " + (" ".join(f'{q} {cr[q]:.4f}' for q in VARS) if cr else "CRPS -"))
        d, lo, hi = K.block_boot(vv - vb, days)
        lines.append(f"    variogram score mean over u, v, T: bar {vb.mean():.4f}, VS {vv.mean():.4f}; VS - bar {d:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        v, fail = B65.judge(S["balloons"], S["vs"], S["shipped"])
        lines.append(f"    VS vs b65 limits: {v}" + (f" (failed: {', '.join(fail)})" if fail else ""))
        better.append(hi < 0)
        meets.append(v == "PASS")
    lines.append("Rule (pre-set): PASS = in both seeds VS - bar interval below 0 AND VS meets all four b65 limits; KILL = VS not better than the bar in either seed; else MISS.")
    lines.append("Verdict: " + judge(better, meets))
    K.report(NAME, lines)


def _selfcheck():
    assert judge([True, True], [True, True]) == "PASS" and judge([False, False], [True, True]).startswith("KILL") and judge([True, False], [True, True]).startswith("MISS")
    rng = np.random.default_rng(0)
    F = rng.normal(size=(200, 42))
    mod = Model(F, rng.normal(size=(200, 3 * K.NH)))
    assert mod.draw(F[:5], 10, rng).shape == (5, 3 * K.NH)
    assert held("USM00072364") in (True, False)


_selfcheck()
if __name__ == "__main__":
    main()
