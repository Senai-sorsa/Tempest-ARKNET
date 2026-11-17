"""23.T1 first read (REPORT ONLY, no rule): what the 1-second NCEI radiosonde profiles (data/t1, 50 m grid, EPZ and MAF, 2024-25) say about shear and Ri<1,
compared with the IGRA balloons the kit scores against (same station, same years, 00 / 12 UTC).
Rows per station: (a) T1 sampled at the 44 model heights (like-for-like with IGRA: layer thickness and sampling the same), (b) IGRA balloons, (c) T1 at 250 m layers (fine structure; not comparable in value to a, b because shear grows as layers get thinner).
Per band (K.BANDS): shear p99 (m/s per km) and the share of layers with Ri < 1.
Also: how many T1 flights match an IGRA balloon time (should be nearly all; IGRA is built from the same flights).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b72_t1_fine.py
Result: docs/results/logs/kit_b72_t1_fine.log
"""
import glob

import numpy as np

import kit_common as K

ZF = None


def load(name):
    z = t = u = v = T = p = None
    for f in sorted(glob.glob(f"data/t1/{name}_20*.npz")):
        d = np.load(f)
        if z is None:
            z, t, u, v, T, p = d["z"], d["time"], d["u"], d["v"], d["T"], d["p"]
        else:
            t, u, v, T, p = (np.concatenate([a, d[k]]) for a, k in ((t, "time"), (u, "u"), (v, "v"), (T, "T"), (p, "p")))
    return z, t, u, v, T, p


def at_heights(z, a, elev):
    """(flights, nz) on the ASL grid z -> (flights, 44) at K.H above ground, linear in height (log in p done by the caller)."""
    zz = K.H + elev
    return np.array([np.interp(zz, z, r, left=np.nan, right=np.nan) if np.isfinite(r).sum() > 50 else np.full(zz.size, np.nan) for r in a])


def stats(u, v, T, p, dz, mask_h=None):
    """-> per band (shear p99, Ri<1 share). u, v, T, p (n, nh); dz layer thickness (nh-1,) in m and band masks from layer mid heights."""
    sh = np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / (dz / 1000.0)
    th = T * (1e5 / p) ** 0.286
    n2 = 9.81 / (0.5 * (th[:, 1:] + th[:, :-1])) * np.diff(th, axis=-1) / dz
    ri = n2 / np.maximum((sh / 1000.0) ** 2, 1e-12)
    out = []
    for m in mask_h:
        s, r = sh[:, m], ri[:, m]
        ok = np.isfinite(r)
        out.append((np.nanpercentile(s, 99) if np.isfinite(s).any() else np.nan, float(((r < 1) & ok).sum() / max(ok.sum(), 1))))
    return out


def main():
    L = ["23.T1 first read: 1-second radiosonde profiles (NCEI C-BUFR, data/t1) vs the IGRA balloons the kit uses; EPZ and MAF, 2024-25, 00 and 12 UTC. Per band: shear p99 [m/s per km] / share of layers with Ri < 1"]
    names = [b for b, _, _ in K.BANDS]
    L.append("source                          " + "  ".join(f"{n:<16}" for n in names))
    for sid, name in ((K.EPZ, "EPZ"), (K.MAF, "MAF")):
        lat, lon, elev = K.station_pos(sid)
        z, t, u, v, T, p = load(name)
        keep = (t >= np.datetime64("2024-01-01")) & (t < np.datetime64("2026-01-01")) & np.isin(t.astype("datetime64[h]").astype(int) % 24, (0, 12))
        t, u, v, T, p = t[keep], u[keep], v[keep], T[keep], p[keep]
        tb, b = K.balloon(sid)
        ib = (tb.year >= 2024) & (tb.year <= 2025) & np.isin(tb.hour, (0, 12))
        tbs = {np.datetime64(x.to_datetime64(), "h") for x in tb[ib]}
        match = sum(np.datetime64(x, "h") in tbs for x in t)
        L.append(f"{name}: {len(t)} T1 flights, {ib.sum()} IGRA balloons, {match} T1 flights with an IGRA balloon of the same hour")
        mid = 0.5 * (K.H[1:] + K.H[:-1])
        masks = [(mid >= lo) & (mid < hi) for _, lo, hi in K.BANDS]
        # (a) T1 at the 44 heights; log p so the interpolation matches the hydrostatic profile
        h44 = {q: at_heights(z, x, elev) for q, x in (("u", u), ("v", v), ("T", T))}
        h44["p"] = np.exp(at_heights(z, np.log(p), elev))
        ok = np.isfinite(h44["u"]).sum(1) >= 30
        sa = stats(h44["u"][ok], h44["v"][ok], h44["T"][ok], h44["p"][ok], np.diff(K.H), masks)
        L.append(f"  {name} T1 at 44 heights    " + "  ".join(f"{a:5.1f} / {r:.3f} " for a, r in sa) + f"  ({ok.sum()} flights)")
        # (b) IGRA balloons
        fb = np.isfinite(b["u"][ib]).sum(1) >= 30
        sb = stats(b["u"][ib][fb], b["v"][ib][fb], b["T"][ib][fb], b["p"][ib][fb], np.diff(K.H), masks)
        L.append(f"  {name} IGRA balloons       " + "  ".join(f"{a:5.1f} / {r:.3f} " for a, r in sb) + f"  ({fb.sum()} balloons)")
        # (c) T1 at 250 m layers (every 5th 50 m grid point), same band limits above ground
        zz = z[::5]
        zm = 0.5 * (zz[1:] + zz[:-1]) - elev
        mk = [(zm >= lo) & (zm < hi) for _, lo, hi in K.BANDS]
        sc = stats(u[:, ::5], v[:, ::5], T[:, ::5], p[:, ::5], np.diff(zz), mk)
        L.append(f"  {name} T1 at 250 m layers  " + "  ".join(f"{a:5.1f} / {r:.3f} " for a, r in sc))
    L.append("Notes: no rule. (a) vs (b) tests whether the balloons the kit scores against see the same shear tail and Ri<1 share as the 1-second data at the same 44 heights; if a is well above b the IGRA truth under-reads fine structure, "
             "and the shortfalls of the tool at 12-18 km (shear p99 0.78 of the balloons, Ri<1 0.062 vs 0.149) would be partly the truth's own sampling. (c) is a finer-layer view only. Source and file counts: docs/results/logs/t1_provenance.log.")
    K.report("b72_t1_fine", L)


if __name__ == "__main__":
    main()
