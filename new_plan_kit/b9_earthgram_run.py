"""Run real Earth-GRAM 2016 (NASA MSFC, PC executable) on the b9 comparison cases and write them in the kit's external format. REPORT ONLY.

Input:  data/kit/gram_cases.csv and data/kit/gram_cases_heights.csv (from b9_gram_compare.py --cases-out).
Runs:   one GRAM run per case: trajectory file = the 44 model heights above sea level at the station (one instant, time 0), geocentric latitude,
        Monte Carlo mc = --m profiles with a per-case seed, NCEP climatology POR 1997-2015 at the case's UTC hour (NCEPhr = 0 -> from ihro).
        --variant ncep : NCEP climatology only (iurra = 0).
        --variant rra  : 2006 Range Reference Atmosphere where one is near (El Paso RRA, 0.3 deg from Santa Teresa; nothing within 2.5 deg of Midland,
                         so Midland is the same as ncep).
Output: data/kit/earthgram_<variant>.npz  (case, u, v, T, p of (n, m, 44); the kit's --extra format)
        data/kit/earthgram_<variant>_clim.npz  (case, GRAM mean and SD of u, v, T, p, rho per height; one row per case; from the first MC run)
The GRAM exe needs the 32-bit VC++ 2013 runtime (msvcr120/msvcp120.dll) next to it in 'PC Executables'.

    .venv/Scripts/python -W ignore new_plan_kit/b9_earthgram_run.py --variant ncep --m 100 --jobs 12
    .venv/Scripts/python -W ignore new_plan_kit/b9_earthgram_run.py --selfcheck
"""
import argparse
import math
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAM = os.path.join(ROOT, "data", "earthgram", "EarthGRAM2016Version2.0")
EXE = os.path.join(GRAM, "PC Executables", "GRAM2016.exe")
KIT = os.path.join(ROOT, "data", "kit")
E2 = 0.00669437999014  # WGS84 first eccentricity squared

NAMELIST = """ $namein_e10
  atmpath = {gram}\\IOfiles\\
  NCEPpath = {gram}\\NCEPdata\\FixedBin\\
  trapath = trj.txt
  prtpath = null
  nprpath = special.txt
  conpath = null
  rrapath = {gram}\\RRAdata\\
  rralist = rrasites.txt
  profile = null
  h1 = 1.0
  phi1 = {lat:.4f}
  thet1 = {lon:.4f}
  f10 = 150.
  f10b = 150.
  ap = 16.3
  s10 = 0.
  s10b = 0.
  xm10 = 0.
  xm10b = 0.
  y10 = 0.
  y10b = 0.
  dstdtc = 0.
  mn = {mn}
  ida = {ida}
  iyr = {iyr}
  ihro = {ihr}
  mino = 0
  seco = 0.0
  dphi = 0.
  dthet = 0.
  dhgt = 0.
  nmax = 0
  delt = 0.0
  iopt = 1
  iaux = 0
  iprt = 0
  inpr = 1
  icon = 0
  NCEPyr = 9715
  NCEPhr = 0
  nr1 = {seed}
  mc = {mc}
  rpscale = {rpscale}
  ruscale = {ruscale}
  rwscale = 1.0
  iurra = {iurra}
  iyrrra = 2
  sitelim = 2.5
  sitenear = 0.5
  initpert = 0
  rdinit = 0.
  rtinit = 0.
  ruinit = 0.
  rvinit = 0.
  rwinit = 0.0
  patchy = 0.0
  itherm = 1
  z0in = -1
  ibltest = 0
 $End
"""
COLS = ["Time", "Hgtkm", "Lat", "Lon", "DensMean", "PresMean", "Tmean", "EWmean", "NSmean", "DensPert", "PresPert", "Tpert", "EWpert", "NSpert",
        "SDden", "SDprs", "SDtemK", "SDuwnd", "SDvwnd"]


def geocentric(lat_gd):
    return math.degrees(math.atan((1 - E2) * math.tan(math.radians(lat_gd))))


def parse_special(path, nh):
    """special.txt -> array (runs, nh, len(COLS)). Header lines (starting with 'Time') are skipped; MC runs follow each other, nh rows each."""
    rows = [ln.split()[:len(COLS)] for ln in open(path) if ln.strip() and not ln.lstrip().startswith("Time")]
    a = np.array(rows, float)
    assert len(a) % nh == 0 and len(a) > 0, f"{path}: {len(a)} rows is not a multiple of {nh} heights"
    return a.reshape(-1, nh, len(COLS))


def run_case(i, row, hts_asl, variant, mc, workroot, keep=False, ruscale=1.0, rpscale=1.0):
    wd = os.path.join(workroot, f"{i:04d}")
    os.makedirs(wd, exist_ok=True)
    t = pd.Timestamp(row.time_utc)
    lat = geocentric(row.lat)
    with open(os.path.join(wd, "trj.txt"), "w") as f:
        for z in hts_asl:
            f.write(f"{0.0:10.3f} {z / 1000:10.4f} {lat:10.4f} {row.lon:10.4f}\n")
    with open(os.path.join(wd, "nl.txt"), "w") as f:
        f.write(NAMELIST.format(gram=GRAM, lat=lat, lon=row.lon, mn=t.month, ida=t.day, iyr=t.year, ihr=t.hour, seed=1000 + 7919 * i, mc=mc,
                                iurra=1 if variant == "rra" else 0, ruscale=ruscale, rpscale=rpscale))
    sp = os.path.join(wd, "special.txt")
    if os.path.exists(sp):
        os.remove(sp)
    r = subprocess.run([EXE], input=wd + "\\\nnl.txt\n\n", capture_output=True, text=True, cwd=wd, timeout=1800)
    if not os.path.exists(sp):
        raise RuntimeError(f"case {i} ({row.case}): GRAM wrote no special.txt\n{r.stdout[-800:]}")
    a = parse_special(sp, len(hts_asl))
    if a.shape[0] != mc:
        raise RuntimeError(f"case {i} ({row.case}): {a.shape[0]} runs in special.txt, expected {mc}")
    if not keep:
        shutil.rmtree(wd, ignore_errors=True)
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("ncep", "rra"), default="ncep")
    ap.add_argument("--m", type=int, default=100)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="first N cases only (smoke)")
    ap.add_argument("--keep", action="store_true", help="keep the per-case run folders")
    ap.add_argument("--ruscale", type=float, default=1.0, help="GRAM wind perturbation scale (sensitivity runs; output name gets _ru<x>)")
    ap.add_argument("--rpscale", type=float, default=1.0, help="GRAM density/T/p perturbation scale (output name gets _rp<x>)")
    a = ap.parse_args()
    cases = pd.read_csv(os.path.join(KIT, "gram_cases.csv"))
    hts = pd.read_csv(os.path.join(KIT, "gram_cases_heights.csv"))
    if a.limit:
        cases = cases.iloc[:a.limit]
    hmap = {s: g.sort_values("height_above_ground_m").height_above_sea_m.values for s, g in hts.groupby("station")}
    work = os.path.join(ROOT, "data", "earthgram", "runs", f"{a.variant}_ru{a.ruscale:g}_rp{a.rpscale:g}")
    os.makedirs(work, exist_ok=True)
    with ThreadPoolExecutor(a.jobs) as ex:
        out = list(ex.map(lambda ir: run_case(ir[0], ir[1], hmap[ir[1].station], a.variant, a.m, work, a.keep, a.ruscale, a.rpscale), cases.iterrows()))
    A = np.stack(out)                                         # (n, m, 44, cols)
    c = {k: j for j, k in enumerate(COLS)}
    tag = (f"_ru{a.ruscale:g}" if a.ruscale != 1 else "") + (f"_rp{a.rpscale:g}" if a.rpscale != 1 else "") + ("_smoke" if a.limit else "")
    np.savez_compressed(os.path.join(KIT, f"earthgram_{a.variant}{tag}.npz"), case=np.array(cases.case.tolist(), dtype=str),
                        u=A[..., c["EWpert"]].astype(np.float32), v=A[..., c["NSpert"]].astype(np.float32),
                        T=A[..., c["Tpert"]].astype(np.float32), p=A[..., c["PresPert"]].astype(np.float32))
    f = A[:, 0]
    np.savez_compressed(os.path.join(KIT, f"earthgram_{a.variant}{tag}_clim.npz"), case=np.array(cases.case.tolist(), dtype=str),
                        u_mean=f[..., c["EWmean"]], v_mean=f[..., c["NSmean"]], T_mean=f[..., c["Tmean"]], p_mean=f[..., c["PresMean"]],
                        rho_mean=f[..., c["DensMean"]], u_sd=f[..., c["SDuwnd"]], v_sd=f[..., c["SDvwnd"]], T_sd=f[..., c["SDtemK"]],
                        p_sd_pct=f[..., c["SDprs"]], rho_sd_pct=f[..., c["SDden"]])
    print(f"wrote earthgram_{a.variant}{tag}.npz: {A.shape[0]} cases x {A.shape[1]} members x {A.shape[2]} heights; "
          f"median T {np.median(A[..., c['Tpert']]):.1f} K, median p {np.median(A[..., c['PresPert']]):.0f} Pa")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        assert abs(geocentric(31.81) - 31.64) < 0.01 and abs(geocentric(32.38) - 32.21) < 0.01 and geocentric(0.0) == 0.0
        print("selfcheck ok")
    else:
        main()
