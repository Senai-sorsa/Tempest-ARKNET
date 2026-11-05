"""Lead-time router and blending between sources (PHASE4_FORECAST.md section 4 and 4.9).

lead = valid time - now, in days. Modes: P past (ERA5 exists), P0 recent past, F days 0-7, F2 days 8-15, M weeks 3-6, C climate model.
Boundaries are settings (defaults below, to be tuned on validation). Blending is a weight on the climate side that rises smoothly from 0 to 1
across a window, so there is no jump in the median or spread between neighbouring leads:
    w_clim(lead) = 0 before `start`, 1 after `end`, a cosine ramp between.
Mixing is done on SAMPLES (draw each sample from the forecast side with probability 1 - w, else from the climate side), which keeps every sample a
whole real profile and gives a proper mixture distribution at the seam.
"""
import numpy as np

DEFAULTS = dict(p_days=-6.0, p0_days=0.0, f_days=7.0, f2_days=15.0, m_days=46.0,
                ens_blend=(10.0, 15.0),   # forecast ensemble -> next source
                m_blend=(35.0, 46.0))     # sub-seasonal -> climate


def check(s):
    """Settings must be strictly ordered and blend windows must have a positive width (review 4.3 / 8.10)."""
    order = [s["p_days"], s["p0_days"], s["f_days"], s["f2_days"], s["m_days"]]
    if any(b <= a for a, b in zip(order, order[1:])):
        raise ValueError(f"router boundaries must be strictly increasing, got {order}")
    for k in ("ens_blend", "m_blend"):
        if not s[k][1] > s[k][0]:
            raise ValueError(f"{k} needs end > start, got {s[k]}")
    return s


def mode(lead_days, s=None):
    s = check({**DEFAULTS, **(s or {})})
    if lead_days <= s["p_days"]:
        return "P"
    if lead_days <= s["p0_days"]:
        return "P0"
    if lead_days <= s["f_days"]:
        return "F"
    if lead_days <= s["f2_days"]:
        return "F2"
    if lead_days <= s["m_days"]:
        return "M"
    return "C"


def ramp(x, start, end):
    """0 before start, 1 after end, cosine between."""
    if not end > start:
        raise ValueError(f"ramp needs end > start, got start={start}, end={end}")
    t = np.clip((np.asarray(x, float) - start) / (end - start), 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def climate_weight(lead_days, s=None):
    """Share of samples that should come from the climate model at this lead (0 = all forecast side)."""
    s = check({**DEFAULTS, **(s or {})})
    lead = np.asarray(lead_days, float)
    w = np.where(lead > s["f2_days"], ramp(lead, *s["m_blend"]), 0.0)
    return float(w) if w.ndim == 0 else w


def ensemble_weight(lead_days, s=None):
    """Share of samples from the live ensemble (versus the sub-seasonal / climate side) in the 10-15 day hand-over."""
    s = {**DEFAULTS, **(s or {})}
    return 1.0 - ramp(lead_days, *s["ens_blend"])


def mix(rng, forecast_samples, other_samples, w_other):
    """Row-wise mixture: sample j comes from `other_samples` with probability w_other, else from `forecast_samples`.
    Both (m, ...) with the same m."""
    m = forecast_samples.shape[0]
    if other_samples.shape != forecast_samples.shape:
        raise ValueError(f"mix needs the same shape on both sides, got {forecast_samples.shape} and {other_samples.shape}")
    if not 0.0 <= float(w_other) <= 1.0:
        raise ValueError(f"mixture weight must be in [0, 1], got {w_other}")
    pick = rng.random(m) < w_other
    out = np.array(forecast_samples, copy=True)
    out[pick] = other_samples[pick]
    return out
