"""16-day forecast extension, step 0 (user 2026-11-17; To-do-Concise 'NEW'). REPORT with a pre-set rule. Is there raw-forecast skill beyond the tested 7 d?
Data: data/raw/wb2_hres_global (HRES, 7,483 world points, leads 6-240 h every 6 h, 2016-22) vs data/raw/era5_global (one hour per day) at the same valid times.
Per lead 5, 7, 8, 9, 10 d and cell (T 850 hPa, u 500 hPa, v 500 hPa): MAE of raw HRES vs ERA5, against the MAE of the same-month ERA5 mean (climate mean, point by point, all other years 2016-22,
no leakage of the valid day's year). skill = 1 - MAE_HRES / MAE_clim.
PRE-SET RULE (before the run): GO to step 1 (train and score a 9-15 d mode F) if skill >= 0.10 in all three cells at 9 d. NARROW if skill >= 0.10 at 8 d but not 9 d (extend only to 8-9 d).
STOP (no extension past 7.5 d beyond a climate blend) if skill < 0.10 at 8 d. HRES stops at 10 d here, so 11-16 d is not testable with this data (needs another source; reported, not scored).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b74_f16_step0.py
Result: docs/results/logs/kit_b74_f16_step0.log
"""
import numpy as np

import kit_common as K

H, E = "data/raw/wb2_hres_global", "data/raw/era5_global"
LEADS = (120, 168, 192, 216, 240)
CELLS = (("t", 850, "T 850"), ("u", 500, "u 500"), ("v", 500, "v 500"))   # level in hPa; the two stores order levels oppositely (HRES 50..1000, ERA5 1000..50)
YEARS = range(2016, 2023)
MONTHS = (1, 4, 7, 10)           # four seasons, all 7 years


def dec(f, n):
    s, o = {c.split()[0]: c.split()[1:] for c in f["code"]}[n]
    return f[n].astype(np.float32) * float(s) + float(o)


def main():
    ecode = np.load(f"{E}/points.npz")["code"]
    err = {(m, L, c[2]): [] for m in MONTHS for L in LEADS for c in CELLS}
    clim_err = {k: [] for k in err}
    for m in MONTHS:
        era, hres = {}, {}
        for y in YEARS:
            e = np.load(f"{E}/{y}-{m:02d}.npz")
            vt = e["valid_time"].astype("datetime64[h]")
            era[y] = (vt, {c[0] + str(c[1]): dec_e for c in CELLS for dec_e in [None]})
            sc = {c[0]: {k.split()[0]: k.split()[1:] for k in ecode}[c[0]] for c in CELLS}
            era[y] = (vt, {(c[0], c[1]): e[c[0]][:, list(e["pressure_level"]).index(c[1]), :].astype(np.float32) * float(sc[c[0]][0]) + float(sc[c[0]][1]) for c in CELLS})
            hres[y] = np.load(f"{H}/{y}{m:02d}.npz")
        for c in CELLS:
            allv = np.concatenate([era[y][1][(c[0], c[1])] for y in YEARS])     # (days, points)
            for y in YEARS:
                vt, ed = era[y]
                others = np.concatenate([era[z][1][(c[0], c[1])] for z in YEARS if z != y])
                mu = others.mean(0)
                h = hres[y]
                hv = dec(h, c[0])[:, list(h["level"]).index(c[1]), :]
                lead, valid = h["lead_h"], h["valid"].astype("datetime64[h]")
                for L in LEADS:
                    for i in np.flatnonzero(lead == L):
                        j = np.flatnonzero(vt == valid[i])
                        if j.size:
                            err[(m, L, c[2])].append(np.abs(hv[i] - ed[c[0], c[1]][j[0]] if False else hv[i] - ed[(c[0], c[1])][j[0]]).mean())
                            clim_err[(m, L, c[2])].append(np.abs(mu - ed[(c[0], c[1])][j[0]]).mean())
    L_ = ["16-day extension step 0: raw HRES vs same-month ERA5 mean, mean absolute error over 7,483 world points, 2016-22, months Jan / Apr / Jul / Oct (skill = 1 - MAE_HRES / MAE_clim)",
          "lead   " + "   ".join(f"{c[2]:<22}" for c in CELLS)]
    sk = {}
    for L in LEADS:
        row = []
        for c in CELLS:
            a = np.mean([x for m in MONTHS for x in err[(m, L, c[2])]])
            b = np.mean([x for m in MONTHS for x in clim_err[(m, L, c[2])]])
            n = sum(len(err[(m, L, c[2])]) for m in MONTHS)
            sk[(L, c[2])] = 1 - a / b
            row.append(f"{a:5.2f} vs {b:5.2f} skill {1 - a / b:+.2f} (n {n})")
        L_.append(f"{L // 24:>3d} d  " + "   ".join(row))
    go9 = all(sk[(216, c[2])] >= 0.10 for c in CELLS)
    go8 = all(sk[(192, c[2])] >= 0.10 for c in CELLS)
    L_.append("VERDICT (pre-set rule): " + ("GO to step 1 (9 d skill >= 0.10 in all cells)" if go9 else "NARROW (8 d only)" if go8 else "STOP (8 d skill < 0.10)"))
    L_.append("Notes: raw deterministic HRES against a climate-mean point forecast, not the tool's probabilistic score; ERA5 is one hour per day, HRES starts 00 / 12 UTC so matched times only. 11-16 d is not testable here (HRES file ends at 10 d).")
    K.report("b74_f16_step0", L_)


if __name__ == "__main__":
    main()
