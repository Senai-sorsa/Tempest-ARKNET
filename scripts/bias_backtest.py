"""IL-98 item B: back-test the online EWMA bias tracker on the real feed. Forecast = Open-Meteo Previous Runs (lead 1..7 d, 2 m temperature and 10 m wind speed) at the two sites, truth = ASOS
hourly reports (Midland MAF for the Midland site, Truth or Consequences TCS for Spaceport America, 30 km away: the tracker's job includes absorbing that offset).

For a forecast with valid time t and lead D (issued D days earlier), the tracker may only use errors (forecast - observation) of the same lead whose valid DAY is at most t_day - D - 1. State: one EWMA per hour of
day, alpha = 1/30 per day. Variants: raw; always subtract the EWMA; gated (at least 20 updates and |bias| > 2 standard errors, as in the plan). Scores: MAE and RMSE on 2024-01 .. latest, per lead, with a
day-block bootstrap interval of the MAE change.
    PYTHONPATH=. python scripts/bias_backtest.py"""
import json
import os

import numpy as np
import pandas as pd

from tempest.ops import logger as lg

PR, ASOS = "data/raw/om_previous_runs", ["data/raw/asos", "data/raw/asos_2026"]
SITE_STATION = {"spaceport_america": "TCS", "midland": "MAF"}
ALPHA, MIN_N, KT = 1 / 30, 20, 0.514444


def obs_series(station):
    frames = []
    for root in ASOS:
        d = os.path.join(root, station)
        if os.path.isdir(d):
            frames += [pd.read_csv(os.path.join(d, f), na_values=["", "M"]) for f in sorted(os.listdir(d)) if f.endswith(".csv")]
    o = pd.concat(frames)
    o["valid"] = pd.to_datetime(o["valid"], utc=True).dt.tz_localize(None)
    o = o[(o.valid.dt.minute >= 40)].copy()                                 # hourly routine report (about :53)
    o["time"] = o.valid.dt.round("h")
    o = o.drop_duplicates("time").set_index("time")
    return pd.DataFrame(dict(t=(o.tmpf - 32) * 5 / 9, ws=o.sknt * KT))


def forecasts(site, model, var, day):
    rows = []
    d = os.path.join(PR, site, model)
    for f in sorted(x for x in os.listdir(d) if x.endswith(".json")):
        h = json.load(open(os.path.join(d, f), encoding="utf-8"))["hourly"]
        rows.append(pd.Series(h[f"{var}_previous_day{day}"], index=pd.to_datetime(h["time"]), dtype=float))
    return pd.concat(rows)


def track(err):
    """err: DataFrame index day x hour (NaN allowed). -> EWMA bias, count, EWMA variance after each day (same shape)."""
    b, v, n = np.zeros(24), np.zeros(24), np.zeros(24)
    B, V, N = [], [], []
    for _, e in err.iterrows():
        e = e.to_numpy()
        ok = np.isfinite(e)
        n = n + ok
        b = np.where(ok, np.where(n == 1, e, (1 - ALPHA) * b + ALPHA * np.nan_to_num(e)), b)
        v = np.where(ok, np.where(n == 1, 0.0, (1 - ALPHA) * v + ALPHA * (np.nan_to_num(e) - b) ** 2), v)
        B.append(b.copy()), V.append(v.copy()), N.append(n.copy())
    idx = err.index
    return pd.DataFrame(B, idx, err.columns), pd.DataFrame(V, idx, err.columns), pd.DataFrame(N, idx, err.columns)


def main():
    out = []
    for site, station in SITE_STATION.items():
        obs = obs_series(station)
        for model in ("ecmwf_ifs025", "gfs_seamless"):
            for var, col in (("temperature_2m", "t"), ("wind_speed_10m", "ws")):
                for D in range(1, 8):
                    f = forecasts(site, model, var, D)
                    df = pd.DataFrame(dict(f=f, o=obs[col])).dropna()
                    df = df[df.index >= "2024-01-01"]
                    df["err"] = df.f - df.o
                    df["day"], df["hour"] = df.index.normalize(), df.index.hour
                    E = df.pivot_table(index="day", columns="hour", values="err").reindex(columns=range(24))
                    E = E.reindex(pd.date_range(E.index.min(), E.index.max()))
                    B, V, N = track(E)
                    # state usable for valid day t: updated through day t - D - 1
                    sh = lambda X: X.shift(D + 1)
                    Bs, Vs, Ns = sh(B), sh(V), sh(N)
                    se = np.sqrt(Vs / (2 / ALPHA - 1))
                    use = (Ns >= MIN_N) & (Bs.abs() > 2 * se)
                    key = df.set_index(["day", "hour"]).index
                    bias = np.array([Bs.at[d, h] if d in Bs.index else np.nan for d, h in key])
                    gate = np.array([bool(use.at[d, h]) if d in use.index else False for d, h in key])
                    ok = np.isfinite(bias)
                    e0 = df.err.to_numpy()[ok]
                    e1 = e0 - bias[ok]
                    e2 = e0 - np.where(gate[ok], bias[ok], 0.0)
                    days = df.day.to_numpy()[ok]
                    u, inv = np.unique(days, return_inverse=True)
                    rng = np.random.default_rng(0)
                    boot = rng.multinomial(len(u), np.full(len(u), 1 / len(u)), 300)
                    def dmae(a, b_):
                        d_ = np.abs(a) - np.abs(b_)
                        s = np.bincount(inv, d_, len(u)); c = np.bincount(inv, minlength=len(u))
                        bs = (boot @ s) / (boot @ c)
                        return d_.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
                    c1, c2 = dmae(e1, e0), dmae(e2, e0)
                    out.append(dict(site=site, model=model, var=var, lead=D, n=int(ok.sum()), mae_raw=np.abs(e0).mean(), mae_always=np.abs(e1).mean(), mae_gated=np.abs(e2).mean(),
                                    d_always=c1[0], always_lo=c1[1], always_hi=c1[2], d_gated=c2[0], gated_lo=c2[1], gated_hi=c2[2], bias_raw=e0.mean(), rmse_raw=np.sqrt((e0 ** 2).mean()), rmse_gated=np.sqrt((e2 ** 2).mean())))
    t = pd.DataFrame(out)
    t.to_csv("models/bias_backtest.csv", index=False)
    with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
        print(t[["site", "model", "var", "lead", "n", "mae_raw", "mae_always", "mae_gated", "d_gated", "gated_lo", "gated_hi", "bias_raw"]].to_string(index=False))
        g = t.groupby(["var"]).apply(lambda x: pd.Series(dict(mean_d_always=x.d_always.mean(), mean_d_gated=x.d_gated.mean(), share_gated_better=(x.gated_hi < 0).mean(), share_gated_worse=(x.gated_lo > 0).mean())))
        print(g.to_string())


if __name__ == "__main__":
    main()
