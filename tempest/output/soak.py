"""Soak history (PHASED_PLAN 3.4, Code-Modifications/atmosphere-outputs.md section 4): pad weather for the 24 h before launch.

The generator gives only the launch hour. A diurnal library supplies the rest: for a sample with launch 2 m temperature
t, take REAL ERA5 24 h histories from the same grid point, the same UTC launch hour, within +/- `window` days of the
date, from training years only; pick one at random among the K whose launch temperature is closest to t; shift its
t2m history by the difference. ssrd and wind histories are kept as they were, so night cooling, sunrise and clouds stay
real. T_soak = exponentially weighted mean of the t2m history with time constant tau (a setting; none is invented).
"""
import numpy as np
import pandas as pd

HOURS = 24


class Library:
    """Real hourly surface history from surface_hourly.zarr, loaded for the library years only."""

    def __init__(self, surface, first_year, last_year, window=15, k=10):
        self.window, self.k = window, k
        t = pd.DatetimeIndex(surface.time.values)
        sel = np.flatnonzero((t.year >= first_year) & (t.year <= last_year))
        self.lo, self.hi = int(sel[0]), int(sel[-1])
        self.t_start = t[self.lo]
        block = slice(self.lo, self.hi + 1)
        self.t2m = surface["t2m"].isel(time=block).values  # (point, time)
        self.ssrd = surface["ssrd"].isel(time=block).values
        self.wind = np.hypot(surface["u10"].isel(time=block).values, surface["v10"].isel(time=block).values)
        self.years = np.arange(first_year, last_year + 1)
        self.n = self.hi - self.lo + 1

    def index_of(self, ts):
        """Timestamps -> integer positions on the hourly axis of the loaded block."""
        return np.asarray((pd.DatetimeIndex(ts) - self.t_start) / pd.Timedelta(hours=1)).astype(np.int64)

    def candidates(self, utc_time):
        """One launch time -> positions of the same UTC hour on nearby days of every library year (24 h of history
        available before each)."""
        ts = pd.Timestamp(utc_time)
        day = ts.replace(day=28) if (ts.month == 2 and ts.day == 29) else ts
        base = [day.replace(year=int(y)) for y in self.years]
        days = pd.to_timedelta(np.arange(-self.window, self.window + 1), unit="D")
        i = self.index_of(pd.DatetimeIndex([b + d for b in base for d in days]))
        return i[(i >= HOURS) & (i < self.n)]

    def draw(self, point, utc_time, t_launch, rng):
        """t_launch (m,) samples of launch t2m (K) -> (t2m_hist, ssrd_hist, wind_hist), each (m, 24), oldest hour first,
        the last column being the launch hour."""
        t_launch = np.asarray(t_launch)
        ci = self.candidates(utc_time)
        tl = self.t2m[point, ci]  # launch temperature of each candidate day
        k = min(self.k, len(ci))
        near = np.argpartition(np.abs(tl[None, :] - t_launch[:, None]), k - 1, axis=1)[:, :k]
        pick = ci[near[np.arange(len(t_launch)), rng.integers(0, k, len(t_launch))]]
        win = pick[:, None] + np.arange(-HOURS + 1, 1)[None, :]
        hist = self.t2m[point, win]
        hist = hist + (t_launch - hist[:, -1])[:, None]  # shift so the launch hour matches the sample
        return hist, self.ssrd[point, win], self.wind[point, win]


def t_soak(t2m_hist, tau_hours):
    """Exponentially weighted mean of the 24 h t2m history (last column = launch hour = weight 1), tau in hours."""
    w = np.exp(-np.arange(HOURS - 1, -1, -1) / float(tau_hours))
    return (t2m_hist * w).sum(-1) / w.sum()


def summary(t2m_hist, tau_hours):
    """Per sample: T_soak, 24 h minimum and maximum."""
    return dict(T_soak=t_soak(t2m_hist, tau_hours), t2m_min24=t2m_hist.min(-1), t2m_max24=t2m_hist.max(-1))
