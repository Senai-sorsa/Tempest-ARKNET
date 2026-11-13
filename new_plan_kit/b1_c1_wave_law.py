"""C1 step 1: does the shear that ERA5 misses rise with stability? PASS / DROP RULE BELOW.
Pairs: EPZ balloons and ERA5 at the nearest point, same hour, 2005-2022. Per pair and layer (between neighbouring model heights):
    d  = (balloon shear)^2 - (ERA5 shear)^2        [1/s^2]
    N2 = Brunt-Vaisala frequency squared from the ERA5 temperature (pressure from the balloon)
Per height band: mean d in three equal-count classes of N2 (day-block 95 % intervals), and c of the fit d = c * N2 through the origin.
PASS: mean d rises class 1 < class 2 < class 3 in BOTH the 1-5 km and the 5-12 km band. Then b2_shear_target_fit.py may use --form c1.
DROP: otherwise. Then C1 is closed and b2_shear_target_fit.py uses the plain ratio (--form ratio, its default).

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_c1_wave_law.py      # 1-2 min, reads the ERA5 store (about 2 GB RAM)
Result: docs/results/logs/kit_b1_c1_wave_law.log and data/kit/c1_wave_law.npz (c per band, used by b2_shear_target_fit.py --form c1)
"""
import os

import numpy as np

import kit_common as K

MID = 0.5 * (K.H[1:] + K.H[:-1])


def fit_c(d, n2):
    """Least squares through the origin: d = c * n2."""
    return float((d * n2).sum() / (n2 * n2).sum())


def main():
    K.ram_gate(6.0)
    lat, lon, _ = K.station_pos(K.EPZ)
    bt, b = K.balloon(K.EPZ)
    keep = (bt.year >= 2005) & (bt.year <= 2022)
    et, e = K.era5_at(lat, lon, bt[keep])
    kb = bt.get_indexer(et)
    sb = (K.shear_mag(b["u"][kb], b["v"][kb]) / 1000.0) ** 2
    se = (K.shear_mag(e["u"], e["v"]) / 1000.0) ** 2
    d, n2 = sb - se, K.n2(e["T"], b["p"][kb])
    day = np.broadcast_to(np.asarray(et.normalize())[:, None], d.shape)
    lines = [f"C1 wave-law check at EPZ, 2005-2022: {len(et)} balloon / ERA5 pairs", "band       class of N2 (low, mid, high): mean d x 1e6 [95 %]                                     c (d = c N2)   rises?"]
    c_band, ok_bands = [], {}
    for name, lo, hi in K.BANDS:
        m = (MID >= lo) & (MID < hi)
        dd, nn, dy = d[:, m], n2[:, m], day[:, m]
        ok = np.isfinite(dd) & np.isfinite(nn)
        dd, nn, dy = dd[ok], nn[ok], dy[ok]
        q = np.quantile(nn, [1 / 3, 2 / 3])
        cls = np.digitize(nn, q)
        means = [K.block_boot(dd[cls == k], dy[cls == k], draws=500) for k in range(3)]
        rises = means[0][0] < means[1][0] < means[2][0]
        c = fit_c(dd, nn)
        c_band.append(c)
        ok_bands[name] = rises
        lines.append(f"{name:<10} " + "  ".join(f"{x[0] * 1e6:7.2f} [{x[1] * 1e6:6.2f}, {x[2] * 1e6:6.2f}]" for x in means) + f"   {c:9.4f}      {'yes' if rises else 'NO'}")
    passed = ok_bands["1-5 km"] and ok_bands["5-12 km"]
    lines.append("VERDICT: C1 PASSES (d rises with N2 in 1-5 and 5-12 km). b2_shear_target_fit.py may be run with --form c1." if passed else
                 "VERDICT: C1 DROPPED (d does not rise with N2 in both bands). Use b2_shear_target_fit.py --form ratio.")
    os.makedirs(K.OUT, exist_ok=True)
    np.savez(os.path.join(K.OUT, "c1_wave_law.npz"), c=np.array(c_band), bands=np.array([n for n, _, _ in K.BANDS]), passed=passed)
    K.report("b1_c1_wave_law", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n2 = rng.random(5000) * 1e-4
    assert abs(fit_c(0.3 * n2 + 1e-6 * rng.standard_normal(5000), n2) - 0.3) < 0.01


_selfcheck()
if __name__ == "__main__":
    main()
