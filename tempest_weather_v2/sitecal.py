"""M6: site calibration from a short on-site wind record (measure-correlate-predict, the wind-energy industry's standard way to turn a few months of mast data and a long reanalysis record into a site wind climate).

    from tempest_weather_v2.sitecal import fit_site, apply_site
    cal = fit_site(reference_speed, site_speed, hours_of_day, method="hourly")      # a month or more of paired hourly values: ERA5 (or tool) speed and the pad anemometer
    corrected = apply_site(cal, speeds, hours_of_day)                              # any speeds from the same reference (the tool's samples, ERA5 hindcasts) at the same hours

Methods (tested on the USCRN basin station against ERA5, 2021-22, campaigns of 1-6 months, scored on the rest of the year, `scripts/mcp_test.py`):
 "ratio"    one scale factor = ratio of means                 (MAE 0.97 -> 0.77 m/s with a 1-month campaign)
 "hourly"   one scale factor per hour of day (24)             (MAE 0.73 with 1 month, 0.70 with 6 months: the best on the error)
 "quantile" the reference speed distribution mapped onto the site's (rank preserving)   (best on the 90th percentile: error -0.03 against -0.40 for the scale; MAE not better)
Speeds only (m/s). The site record and the reference must be in the same height convention (a 1.5 m anemometer corrects to a 1.5 m wind; the factor includes the height ratio). Stdlib + numpy.
"""
import numpy as np

__all__ = ["fit_site", "apply_site", "METHODS", "tcs_speed_factor"]

METHODS = ("ratio", "hourly", "quantile")


def fit_site(reference, site, hours=None, method="hourly", min_per_hour=20):
    """-> calibration dict. reference, site: paired hourly speeds (same length); hours: hour of day (0-23) of each pair, needed for method 'hourly'."""
    r, s = np.asarray(reference, float), np.asarray(site, float)
    if r.shape != s.shape or r.size < 100:
        raise ValueError("need at least 100 paired hourly values of the same length")
    ok = np.isfinite(r) & np.isfinite(s)
    r, s = r[ok], s[ok]
    if r.size < 100:   # audit #26: count the usable pairs, not the NaN-padded input
        raise ValueError("need at least 100 finite paired hourly values")
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if r.mean() <= 0:
        raise ValueError("the reference speeds are all zero")
    cal = dict(method=method, n=int(r.size), ratio=float(s.mean() / r.mean()))
    if method == "hourly":
        if hours is None:
            raise ValueError("method 'hourly' needs the hour of day of every pair")
        h = np.asarray(hours)[ok].astype(int) % 24
        f = np.full(24, cal["ratio"])
        for k in range(24):
            m = h == k
            if m.sum() >= min_per_hour and r[m].mean() > 0:
                f[k] = s[m].mean() / r[m].mean()
        cal["hourly"] = f
    elif method == "quantile":
        q = np.linspace(0.01, 0.99, 99)
        cal["src"], cal["dst"] = np.quantile(r, q), np.quantile(s, q)
    return cal


def apply_site(cal, speeds, hours=None):
    """Corrected speeds (same shape as `speeds`)."""
    x = np.asarray(speeds, float)
    if cal["method"] == "ratio":
        return x * cal["ratio"]
    if cal["method"] == "hourly":
        if hours is None:
            raise ValueError("method 'hourly' needs the hour of day")
        return x * cal["hourly"][np.asarray(hours).astype(int) % 24]
    lo, hi = cal["src"], cal["dst"]
    out = np.interp(x, lo, hi)
    over = x > lo[-1]
    d = lo[-1] - lo[-2]
    slope = (hi[-1] - hi[-2]) / d if d > 1e-6 else (hi[-1] / lo[-1] if lo[-1] > 0 else 1.0)   # audit #26: tied top knots -> the ratio, not a 1e9 slope
    return np.where(over, hi[-1] + (x - lo[-1]) * slope, out)         # beyond the last knot: continue with the last slope


# IL-207b (ASK_LATER 24, adopted 2026-11-11, opt-in): the tool is too calm at the TCS ASOS station (bias +1.44 m/s, worst warm afternoons).
# Factor per local hour block x season, mean of the two fits in docs/results/logs/kit_b3_il207b_site_shift.log (fit 2021-22, test 2023-25:
# CRPS -0.079 and -0.075, coverage 0.81 -> 0.85-0.86). Untested outside 08-20 local -> 1.0 there. For TCS itself only, NOT the pad 30 km away
# (the offset may be the airport's exposure). The two fits differ most at 16-20 warm (1.20 / 1.38).
TCS_SPEED_FACTOR = {"08-11/cool": 0.985, "08-11/warm": 1.015, "12-15/cool": 1.135, "12-15/warm": 1.135, "16-20/cool": 1.06, "16-20/warm": 1.29}


def tcs_speed_factor(when):
    """Opt-in site_cal for a launch at the TCS station on the date of `when` (datetime; naive = UTC): method "hourly", 24 UTC-hour factors.
    Use: Launch(..., site_cal=tcs_speed_factor(t)) or L.calibrate_site(tcs_speed_factor(t))."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    z = ZoneInfo("America/Denver")
    day = (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()
    f = np.ones(24)
    for h in range(24):
        loc = datetime(day.year, day.month, day.day, h, tzinfo=timezone.utc).astimezone(z)
        if 8 <= loc.hour <= 20:
            block = "08-11" if loc.hour < 12 else "12-15" if loc.hour < 16 else "16-20"
            f[h] = TCS_SPEED_FACTOR[block + ("/warm" if 3 <= loc.month <= 8 else "/cool")]
    return {"method": "hourly", "hourly": f}
