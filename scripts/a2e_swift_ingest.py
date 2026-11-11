"""TTU SWiFT 200 m tower (A2e / DOE Wind Data Hub): 50 Hz hourly .dat files -> 1-min and 10-min statistics.

Reads every tower.z01.00.<date>.<time>.ttu200m.dat in SRC (default ~/Downloads/TTU SWiFT Wind data), computes
per height and per window: mean wind (north/west components, horizontal speed, direction from the vector mean),
std of stream / cross / vertical wind, TKE, friction velocity, max 3 s gust, temperature (C), pressure, RH, valid count.
Writes data/raw/a2e/ttu_swift_200m/processed/swift_{1min,10min}.csv (UTC, one row per window, columns <var>_<height>ft)
plus coverage.csv and README.txt. With --move the raw .dat files are then MOVED (same drive, rename) into
data/raw/a2e/ttu_swift_200m/raw_50hz/ (never deleted, never modified). Raw files are only moved after the CSVs are written
and the row counts check out.
Assumptions (stated in README.txt): temperature columns are deg F (header says so) and are converted to deg C; 'time' is UTC;
wind direction is the meteorological direction the wind comes from. The file's own wdir column satisfies
wdir = atan2(-vwest, unorth) (checked on the first rows), so the same formula is applied to the window means; the component
names in the file do not follow the usual sign (unorth is positive for wind FROM the north), so we keep the source names."""
import argparse, shutil, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DST = ROOT / "data" / "raw" / "a2e" / "ttu_swift_200m"
HEIGHTS_FT = [3, 8, 13, 33, 55, 155, 245, 382, 519, 656]
FT = 0.3048
FS = 50  # Hz (0.02 s steps)
GUST_N = 3 * FS
PER = ["unorth", "vwest", "w", "ustream", "vcross", "wdir", "tsonic", "t", "p", "rh"]


def nan_rolling_mean(x, n):
    """Trailing n-sample mean of a 1-D series, NaN if any NaN inside the window."""
    c = np.concatenate([[0.0], np.cumsum(np.where(np.isnan(x), 0.0, x))])
    bad = np.concatenate([[0], np.cumsum(np.isnan(x).astype(np.int64))])
    out = (c[n:] - c[:-n]) / n
    out[(bad[n:] - bad[:-n]) > 0] = np.nan
    return np.concatenate([np.full(n - 1, np.nan), out])


def stats_for(df, win_s):
    """Return a DataFrame, one row per window of win_s seconds, for one hourly frame."""
    t = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S.%f")
    t0 = t.iloc[0].floor("h")
    wid = ((t - t0).dt.total_seconds() // win_s).astype(int).to_numpy()
    nwin = wid.max() + 1
    rows = {"time_utc": [(t0 + pd.Timedelta(seconds=int(i) * win_s)).strftime("%Y-%m-%dT%H:%M:%S") for i in range(nwin)]}
    order = np.argsort(wid, kind="stable")
    bounds = np.searchsorted(wid[order], np.arange(nwin + 1))
    for h in HEIGHTS_FT:
        g = {k: df[f"{k}_{h}ft"].to_numpy(float)[order] for k in PER}
        spd = np.hypot(g["unorth"], g["vwest"])
        gust = nan_rolling_mean(spd, GUST_N)  # on window-sorted series, so windows stay contiguous
        cols = {k: [] for k in ["unorth", "vwest", "w", "speed", "dir", "sd_stream", "sd_cross", "sd_w", "tke", "ustar",
                                "gust3s", "t_C", "tsonic_C", "p_kPa", "rh", "n_valid"]}
        for i in range(nwin):
            s = slice(bounds[i], bounds[i + 1])
            un, vw, ww, us, vc = g["unorth"][s], g["vwest"][s], g["w"][s], g["ustream"][s], g["vcross"][s]
            ok = np.isfinite(un) & np.isfinite(vw) & np.isfinite(ww)
            nv = int(ok.sum())
            cols["n_valid"].append(nv)
            if nv < 0.5 * (bounds[i + 1] - bounds[i]) or nv < 10:  # <50 % valid: blank the window
                for k in cols:
                    if k != "n_valid": cols[k].append(np.nan)
                continue
            u, v, w = un[ok], vw[ok], ww[ok]
            mu, mv, mw = u.mean(), v.mean(), w.mean()
            cols["unorth"].append(mu); cols["vwest"].append(mv); cols["w"].append(mw)
            cols["speed"].append(np.hypot(u, v).mean())
            cols["dir"].append(np.degrees(np.arctan2(-mv, mu)) % 360)  # convention verified against the file's own wdir column
            sdu, sdv, sdw = u.std(), v.std(), w.std()
            su, sc = us[ok], vc[ok]
            cols["sd_stream"].append(np.nanstd(su)); cols["sd_cross"].append(np.nanstd(sc)); cols["sd_w"].append(sdw)
            cols["tke"].append(0.5 * (np.nanvar(su) + np.nanvar(sc) + sdw ** 2))
            cuw = np.mean((u - mu) * (w - mw)); cvw = np.mean((v - mv) * (w - mw))
            cols["ustar"].append((cuw ** 2 + cvw ** 2) ** 0.25)
            gg = gust[s]
            cols["gust3s"].append(np.nanmax(gg) if np.isfinite(gg).any() else np.nan)
            for name, key, conv in (("t_C", "t", True), ("tsonic_C", "tsonic", True), ("p_kPa", "p", False), ("rh", "rh", False)):
                x = g[key][s]
                m = np.nanmean(x) if np.isfinite(x).any() else np.nan
                cols[name].append((m - 32.0) * 5.0 / 9.0 if conv else m)
        for k, vals in cols.items():
            rows[f"{k}_{h}ft"] = vals
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path.home() / "Downloads" / "TTU SWiFT Wind data"))
    ap.add_argument("--limit", type=int, default=0, help="process only the first N files (test); never combined with --move")
    ap.add_argument("--move", action="store_true", help="after processing, move raw .dat files into raw_50hz/")
    a = ap.parse_args()
    src = Path(a.src)
    files = sorted(src.glob("tower.z01.*.ttu200m.dat"))
    if a.limit: files = files[:a.limit]; a.move = False
    if not files: sys.exit(f"no files in {src}")
    out = DST / "processed"; out.mkdir(parents=True, exist_ok=True)
    d1, d10, cov = [], [], []
    for n, f in enumerate(files, 1):
        df = pd.read_csv(f, comment="%", index_col=False, na_values=["NaN", "nan"], low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        df = df[df["time"].astype(str).str.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")]
        s1, s10 = stats_for(df, 60), stats_for(df, 600)
        d1.append(s1); d10.append(s10)
        nvalid = {h: float(np.isfinite(df[f"w_{h}ft"]).mean()) for h in HEIGHTS_FT}
        cov.append({"file": f.name, "rows": len(df), **{f"valid_w_{h}ft": round(nvalid[h], 4) for h in HEIGHTS_FT}})
        print(f"[{n}/{len(files)}] {f.name}: {len(df)} rows, valid w@{HEIGHTS_FT[-1]}ft {nvalid[HEIGHTS_FT[-1]]:.2f}", flush=True)
    suffix = "_test" if a.limit else ""
    p1 = pd.concat(d1, ignore_index=True); p10 = pd.concat(d10, ignore_index=True)
    p1.to_csv(out / f"swift_1min{suffix}.csv", index=False, float_format="%.5g")
    p10.to_csv(out / f"swift_10min{suffix}.csv", index=False, float_format="%.5g")
    pd.DataFrame(cov).to_csv(out / f"coverage{suffix}.csv", index=False)
    (out / "README.txt").write_text(
        "TTU SWiFT 200 m tower, 10 levels (ft above ground): " + ", ".join(map(str, HEIGHTS_FT)) + "\n"
        "(m: " + ", ".join(f"{h*FT:.1f}" for h in HEIGHTS_FT) + "). Source: 50 Hz hourly files in ../raw_50hz/.\n"
        "swift_1min.csv / swift_10min.csv: one row per window start (UTC, ISO). Columns <var>_<h>ft:\n"
        " unorth, vwest (m/s, window mean, source names and signs kept), w (m/s), speed (m/s, mean of instantaneous horizontal speed),\n"
        " dir (deg, meteorological, from vector mean), sd_stream / sd_cross / sd_w (m/s), tke (m2/s2), ustar (m/s, from u'w', v'w'),\n"
        " gust3s (m/s, max 3 s running mean of horizontal speed in the window), t_C (air), tsonic_C (sonic virtual temp; source\n"
        " header unit is deg F for all temperatures, converted), p_kPa, rh (%), n_valid (samples with finite u, v, w).\n"
        "Windows with < 50 % valid samples are blank. Assumptions: time is UTC; unorth = northward, vwest = westward wind; dir computed\n"
        "as the direction the wind comes from. Not yet validated against ERA5 / the tool.\n", encoding="utf-8")
    exp = len(files) * 60
    short = [c["file"] for c in cov if c["rows"] < 180000 * 0.999]
    assert len(p1) <= exp and len(p10) <= len(files) * 6
    if short: print(f"NOTE: {len(short)} files hold less than a full hour (partial hour in source, kept as is): {short}")
    print(f"wrote {len(p1)} 1-min rows and {len(p10)} 10-min rows to {out}")
    if a.move:
        rawd = DST / "raw_50hz"; rawd.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.move(str(f), str(rawd / f.name))
        print(f"moved {len(files)} raw files to {rawd}")


if __name__ == "__main__":
    main()
