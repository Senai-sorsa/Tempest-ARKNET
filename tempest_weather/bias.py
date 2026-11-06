"""Online bias state for the live forecast feed (IL-98 item B), numpy + json only.

State file (written by scripts/update_bias.py) per site and model:
    {"site": ..., "model": ..., "lat": ..., "lon": ..., "updated": "YYYY-MM-DD", "alpha": 1/30,
     "temperature_2m": {"1": {"b": [24 floats], "n": [24], "se": [24]}, ... "7": {...}},
     "wind_speed_10m": {...}}
b = EWMA of (forecast - observation) per hour of day (UTC) at that lead in days. `correction` returns what to subtract for a forecast valid at a given hour, only where the
state has at least MIN_N updates and |b| > 2 se (the gate that the back-test, scripts/bias_backtest.py, used). Only for queries within MAX_KM of the site the state was built for.
"""
import json
import os

import numpy as np

MIN_N = 20
MAX_KM = 60.0


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find(bias_dir, lat, lon, model="ecmwf_ifs025"):
    """The state of the nearest site within MAX_KM, or None."""
    if not bias_dir or not os.path.isdir(bias_dir):
        return None
    best = None
    for f in os.listdir(bias_dir):
        if f.endswith(f"_{model}.json"):
            s = load(os.path.join(bias_dir, f))
            d = np.hypot((s["lat"] - lat) * 111.0, (s["lon"] - lon) * 111.0 * np.cos(np.radians(lat)))
            if d <= MAX_KM and (best is None or d < best[0]):
                best = (d, s)
    return None if best is None else best[1]


def correction(state, variable, lead_days, hour_utc):
    """What to subtract from the forecast of `variable` (K for 2 m temperature, m/s for 10 m wind speed); 0.0 when the gate is closed or no state."""
    if state is None or variable not in state:
        return 0.0
    k = str(int(np.clip(round(lead_days), 1, 7)))
    e = state[variable].get(k)
    if e is None:
        return 0.0
    h = int(hour_utc) % 24
    b, n, se = e["b"][h], e["n"][h], e["se"][h]
    return float(b) if (n >= MIN_N and abs(b) > 2 * se) else 0.0


def apply_to_fields(fields, state, lead_days, hour_utc):
    """Correct t2m and the 10 m wind speed of a forecast `fields` dict in place; the wind direction is kept. -> (dT, dWS) applied."""
    dT = correction(state, "temperature_2m", lead_days, hour_utc)
    dW = correction(state, "wind_speed_10m", lead_days, hour_utc)
    fields["t2m"] = fields["t2m"] - dT
    ws = float(np.hypot(fields["u10"], fields["v10"]))
    if ws > 1e-6 and dW:
        new = max(ws - dW, 0.0)
        fields["u10"], fields["v10"] = fields["u10"] * new / ws, fields["v10"] * new / ws
    return dT, dW
