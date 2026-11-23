"""Weather at a launch site for a given day, from Tempest-ARKNET.

    from tempest_arknet import LaunchSite, profile, monte_carlo, launch_window
    site = LaunchSite("West TX", lat=31.024, lon=-103.6616, elev_m=900)
    prof = profile(site, "2026-06-15 13:00", tz="America/Chicago")
    prof.mean          # mean + standard deviation per altitude
    prof.sigma(-3)     # mean - 3 sigma profile
    mc = monte_carlo(site, "2026-06-15 13:00", tz="America/Chicago", n=500)
    mc.runs            # one row per run per altitude
    mc.percentiles([5, 50, 95])

Same interface as the earthgram package (dynamics/tools/weather/earthgram); the engine is
tempest_weather.api.atmosphere_set: n whole, vertically coherent atmospheres at 44 heights
from 10 m to 18 km above ground, from ERA5 (past), the IFS forecast (0.75-7.5 days ahead)
or the calibrated climate generator (further ahead). `Profile.info` says which answered.
The mean and standard deviations are statistics of those samples.

Coverage: only the trained regions (NM/TX 31-34 N, 108-101 W; Denver 38-40 N, 106-104 W).
Anywhere else raises ValueError; nothing is extrapolated. Top: 18 km above the site.

Units: SI. Altitude in m above MSL, temp in K, p in Pa, rho in kg/m^3, winds in m/s
(u toward east, v toward north), rh in %, dir_from in deg clockwise from north (the
direction the wind blows from).
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from tempest_weather import _core
from tempest_weather import api as tw

STATE = ["temp", "p", "rho", "u", "v"]
TOP_AGL_M = float(_core.HEIGHTS[-1])  # 18 km: the model's top
LOG_INTERP = ("p", "rho")             # interpolated in log space between model heights


class TempestNotFound(RuntimeError):
    pass


def check_install() -> Path:
    """Raise TempestNotFound with a clear reason if no Tempest asset set is present."""
    root = Path(tw.HERE)
    if not tw.regions():
        raise TempestNotFound(f"no Tempest-ARKNET asset sets (assets*/manifest.json) in {root}; "
                              "copy them in or rebuild with python -m tempest.export_tool")
    return root


def is_installed() -> bool:
    try:
        check_install()
        return True
    except TempestNotFound:
        return False


@dataclass(frozen=True)
class LaunchSite:
    name: str
    lat: float      # geodetic deg N
    lon: float      # deg E (west negative)
    elev_m: float   # ground height above MSL


def _utc(when, tz: str | None) -> pd.Timestamp:
    t = pd.Timestamp(when)
    if t.tzinfo is None:
        if tz is None:
            raise ValueError("give a timezone-aware time or tz= (e.g. tz='America/Chicago' or 'UTC')")
        t = t.tz_localize(tz)
    return t.tz_convert("UTC")


def wind_dir_from(u, v):
    """Meteorological direction the wind blows FROM, deg clockwise from north."""
    return np.mod(np.degrees(np.arctan2(-u, -v)), 360.0)


def _altitudes(site: LaunchSite, top_m: float | None, step_m: float) -> np.ndarray:
    top = site.elev_m + TOP_AGL_M if top_m is None else top_m
    if top <= site.elev_m:
        raise ValueError("top_m must be above the site elevation")
    if top > site.elev_m + TOP_AGL_M + 1e-6:
        raise ValueError(f"top_m {top:.0f} m is above Tempest-ARKNET's top, 18 km above the site "
                         f"({site.elev_m + TOP_AGL_M:.0f} m MSL here)")
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    nmax = int(np.floor((top - site.elev_m) / step_m + 1e-9)) + 1
    return site.elev_m + step_m * np.arange(nmax)


def _columns(atm: dict, elev_m: float, alt_m: np.ndarray) -> dict[str, np.ndarray]:
    """Tempest samples -> {column: (n runs, n altitudes)} on `alt_m` (m MSL).

    The ground (0 m above the site) takes the 2 m temperature/humidity and the surface
    pressure; the wind and w below the lowest model height (10 m) are held at their 10 m value.
    """
    t2m, sp, rh2m = (np.asarray(atm[k], np.float64) for k in ("t2m", "sp", "rh2m"))
    tv0 = t2m * (1 + (_core.RV / _core.RD - 1) * _core.mixing_q(t2m, rh2m, sp))
    n = len(t2m)
    w = atm.get("w")
    ground = {"temp": t2m, "p": sp, "rho": sp / (_core.RD * tv0), "rh": rh2m,
              "sos": np.sqrt(_core.GAMMA * _core.RD * tv0),
              "u": atm["u"][:, 0], "v": atm["v"][:, 0], "w": np.full(n, np.nan) if w is None else w[:, 0]}
    above = {"temp": atm["T"], "p": atm["p"], "rho": atm["rho"], "rh": atm["RH"], "sos": atm["a"],
             "u": atm["u"], "v": atm["v"], "w": np.full((n, _core.NH), np.nan) if w is None else w}
    z = np.concatenate([[0.0], _core.HEIGHTS.astype(np.float64)])
    zq = alt_m - elev_m
    out = {}
    for c in ground:
        col = np.column_stack([ground[c], np.asarray(above[c], np.float64)])
        if c in LOG_INTERP:
            col = np.log(col)
        col = np.stack([np.interp(zq, z, row) for row in col])
        out[c] = np.exp(col) if c in LOG_INTERP else col
    return out


def _mean_table(alt_m: np.ndarray, cols: dict[str, np.ndarray]) -> pd.DataFrame:
    """Per-altitude mean and standard deviation over the runs, laid out like earthgram's Profile.mean."""
    speed = np.hypot(cols["u"], cols["v"])
    m = {"alt_m": alt_m}
    for c in (*STATE, "rh"):
        m[c] = cols[c].mean(0)
    for c in (*STATE, "rh"):
        m[f"{c}_sd"] = cols[c].std(0, ddof=1) if len(speed) > 1 else np.zeros(len(alt_m))
    m["speed"] = speed.mean(0)  # mean scalar speed, as GRAM's SpdAvg
    m["speed_sd"] = speed.std(0, ddof=1) if len(speed) > 1 else np.zeros(len(alt_m))
    m["sos"] = cols["sos"].mean(0)
    m["dir_from"] = wind_dir_from(m["u"], m["v"])
    return pd.DataFrame(m)


def _runs_table(alt_m: np.ndarray, cols: dict[str, np.ndarray]) -> pd.DataFrame:
    n, k = cols["u"].shape
    r = {"run": np.repeat(np.arange(n), k), "alt_m": np.tile(alt_m, n)}
    for c in STATE:
        r[c] = cols[c].ravel()
    r["speed"] = np.hypot(r["u"], r["v"])
    r["dir_from"] = wind_dir_from(r["u"], r["v"])
    for c in ("w", "sos", "rh"):
        r[c] = cols[c].ravel()
    return pd.DataFrame(r)


def _sample(site: LaunchSite, when, tz, n, seed, top_m, step_m, kw):
    if n < 1:
        raise ValueError("n must be >= 1")
    alt_m = _altitudes(site, top_m, step_m)
    t = _utc(when, tz)
    check_install()
    atm, info = tw.atmosphere_set(site.lat, site.lon, t.to_pydatetime(), n=n, seed=seed, elevation=site.elev_m, **kw)
    return t, alt_m, _columns(atm, site.elev_m, alt_m), info


@dataclass
class Profile:
    """Mean atmosphere and its standard deviations above a site at one time.

    `mean` has one row per altitude: the mean state, its standard deviations, the mean
    wind SPEED (`speed`, the average scalar speed, so larger than the length of the mean
    wind vector) and the mean wind's direction (`dir_from`). `info` is Tempest's answer
    metadata: mode (past / forecast / ai), source, quality flags.
    """
    site: LaunchSite
    time_utc: pd.Timestamp
    mean: pd.DataFrame = field(repr=False)
    info: dict = field(default_factory=dict, repr=False)

    def sigma(self, k: float) -> pd.DataFrame:
        """mean + k*sd for each quantity (temp, p, rho, u, v, speed), each shifted independently.

        This is a quick bounding case, not a physically consistent atmosphere; use
        monte_carlo() for dispersion.
        """
        m = self.mean
        out = m[["alt_m"]].copy()
        for c in (*STATE, "speed"):
            out[c] = m[c] + k * m[f"{c}_sd"]
        out["speed"] = out["speed"].clip(lower=0.0)
        out["dir_from"] = m["dir_from"]
        return out

    def at(self, alt_m: float) -> pd.Series:
        """Mean profile linearly interpolated to one altitude (m above MSL)."""
        m = self.mean
        if not m["alt_m"].min() <= alt_m <= m["alt_m"].max():
            raise ValueError(f"{alt_m} m is outside the profile")
        return pd.Series({c: np.interp(alt_m, m["alt_m"], m[c]) for c in m.columns if c != "dir_from"})


@dataclass
class MonteCarlo(Profile):
    """`n` whole Tempest atmospheres (coherent with height) plus the mean they scatter around.

    `runs` has one row per run per altitude, ordered run by run.
    """
    runs: pd.DataFrame = field(default=None, repr=False)

    @property
    def n(self) -> int:
        return len(self.runs) // len(self.mean)

    def values(self, col: str) -> np.ndarray:
        """`col` of every run as an (n runs, n altitudes) array."""
        return self.runs[col].to_numpy().reshape(self.n, len(self.mean))

    def percentiles(self, q=(5, 50, 95), cols=(*STATE, "speed")) -> pd.DataFrame:
        """One row per altitude; columns like temp_p5, temp_p50, temp_p95, speed_p95."""
        out = {"alt_m": self.mean["alt_m"].to_numpy()}
        for c in cols:
            for p, row in zip(q, np.percentile(self.values(c), q, axis=0)):
                out[f"{c}_p{p:g}"] = row
        return pd.DataFrame(out)

    def run_profile(self, i: int) -> pd.DataFrame:
        if not 0 <= i < self.n:
            raise IndexError(f"run {i} of {self.n}")
        nlev = len(self.mean)
        return self.runs.iloc[i * nlev:(i + 1) * nlev].drop(columns="run").reset_index(drop=True)


def profile(site: LaunchSite, when, tz: str | None = None, *, top_m: float | None = None,
            step_m: float = 250, n: int = 1024, seed: int = 1234, **tempest) -> Profile:
    """Mean and standard deviation profile above `site` at `when` (local time with tz=, or aware).

    Statistics of `n` Tempest atmospheres. `top_m` defaults to 18 km above the site.
    Extra keywords go to tempest_weather.api.atmosphere_set (mode=, era5_store=, assets=, ...).
    """
    t, alt_m, cols, info = _sample(site, when, tz, n, seed, top_m, step_m, tempest)
    return Profile(site, t, _mean_table(alt_m, cols), info)


def monte_carlo(site: LaunchSite, when, tz: str | None = None, *, n: int = 100, seed: int = 1234,
                top_m: float | None = None, step_m: float = 250, **tempest) -> MonteCarlo:
    """`n` Tempest atmospheres. Same seed -> same atmospheres."""
    t, alt_m, cols, info = _sample(site, when, tz, n, seed, top_m, step_m, tempest)
    return MonteCarlo(site, t, _mean_table(alt_m, cols), info, _runs_table(alt_m, cols))


def launch_window(site: LaunchSite, date, tz: str, hours=range(9, 18), *, top_m: float | None = None,
                  step_m: float = 250, **kw) -> pd.DataFrame:
    """Mean profiles for each local hour on `date`, stacked with a `local_time` column."""
    day = pd.Timestamp(date).normalize()
    frames = []
    for h in hours:
        local = (day + pd.Timedelta(hours=h)).tz_localize(tz)
        frames.append(profile(site, local, top_m=top_m, step_m=step_m, **kw).mean.assign(local_time=local))
    out = pd.concat(frames, ignore_index=True)
    return out[["local_time", *out.columns[:-1]]]
