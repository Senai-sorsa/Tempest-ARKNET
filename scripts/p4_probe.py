"""Phase 4 step 4.0: probe what the Open-Meteo forecast APIs really offer. Writes data/p4/probe.json and prints a summary.

    python scripts/p4_probe.py

Each test is a small request (a day or two of data at the Midland site). For history start dates a few probe dates are tried
and the first with real (non-null) values wins. Gentle: one request every few seconds, retry once on rate limits.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = dict(latitude=31.94, longitude=-102.19)
OUT = "data/p4/probe.json"


def get(base, params, tries=3):
    url = base + "?" + urllib.parse.urlencode({**SITE, **params}, safe=",")
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tempest-probe"}), timeout=120) as r:
                return 200, json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                body = json.loads(body)
            except ValueError:
                pass
            if e.code == 429:
                time.sleep(30 * (k + 1))
                continue
            return e.code, body
        except Exception as e:  # noqa: BLE001
            time.sleep(10)
            err = repr(e)
    return -1, err


def nonnull(doc, block="hourly"):
    """-> {variable: share of non-null values} for a response, or None."""
    if not isinstance(doc, dict) or block not in doc:
        return None
    out = {}
    for k, v in doc[block].items():
        if k != "time" and isinstance(v, list) and v:
            out[k] = round(sum(x is not None for x in v) / len(v), 3)
    return out


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    res = {}
    # 1. Historical forecast API: pressure levels and start dates per model
    for model in ("ecmwf_ifs025", "ecmwf_ifs", "gfs_global", "gfs_seamless", "ecmwf_aifs025_single", "icon_global"):
        hist = {}
        for date in ("2018-06-01", "2021-06-01", "2022-06-01", "2023-06-01", "2024-06-01", "2025-06-01"):
            st, doc = get("https://historical-forecast-api.open-meteo.com/v1/forecast",
                          dict(hourly="temperature_500hPa,wind_speed_850hPa,relative_humidity_700hPa,temperature_2m", models=model,
                               start_date=date, end_date=date, timezone="UTC"))
            hist[date] = nonnull(doc) if st == 200 else dict(status=st, detail=str(doc)[:150])
            time.sleep(3)
        res[f"historical_forecast/{model}"] = hist
    # 2. Previous Runs API
    prev = {}
    for name, hourly in (("surface_previous_day1", "temperature_2m_previous_day1"), ("surface_previous_day5", "temperature_2m_previous_day5"),
                         ("pressure_previous_day1", "temperature_500hPa_previous_day1"), ("pressure_alt", "temperature_500hPa_previous_day1,temperature_2m")):
        for model in ("ecmwf_ifs025", "gfs_global"):
            st, doc = get("https://previous-runs-api.open-meteo.com/v1/forecast", dict(hourly=hourly, models=model, start_date="2025-06-01", end_date="2025-06-02", timezone="UTC"))
            prev[f"{name}/{model}"] = nonnull(doc) if st == 200 else dict(status=st, detail=str(doc)[:200])
            time.sleep(3)
    res["previous_runs"] = prev
    # 3. Single Runs API
    single = {}
    for model in ("ecmwf_ifs025", "ecmwf_ifs", "gfs_global"):
        for run in ("2024-06-01T00:00", "2025-06-01T00:00", "2026-09-01T00:00", "2026-10-20T00:00"):
            st, doc = get("https://single-runs-api.open-meteo.com/v1/forecast", dict(hourly="temperature_500hPa,temperature_2m", models=model, run=run, forecast_days=8, timezone="UTC"))
            single[f"{model}/{run}"] = (nonnull(doc) if st == 200 else dict(status=st, detail=str(doc)[:120]))
            time.sleep(3)
    res["single_runs"] = single
    # 4. Seasonal API (EC46) and archived runs
    seas = {}
    st, doc = get("https://seasonal-api.open-meteo.com/v1/seasonal", dict(daily="temperature_2m_mean", models="ecmwf_ec46", forecast_days=46, timezone="UTC"))
    seas["live_ec46"] = dict(status=st, members=sum(k.startswith("temperature_2m_mean") for k in doc.get("daily", {})) if st == 200 else None,
                             days=len(doc.get("daily", {}).get("time", [])) if st == 200 else None)
    for var in ("temperature_500hPa_mean", "wind_speed_850hPa_mean", "temperature_2m_max"):
        st, doc = get("https://seasonal-api.open-meteo.com/v1/seasonal", dict(daily=var, models="ecmwf_ec46", forecast_days=10, timezone="UTC"))
        seas[f"var/{var}"] = dict(status=st, detail=(str(doc)[:150] if st != 200 else "ok"))
        time.sleep(3)
    for past in ("2025-06-01", "2023-06-01"):
        st, doc = get("https://seasonal-api.open-meteo.com/v1/seasonal", dict(daily="temperature_2m_mean", models="ecmwf_ec46", start_date=past, end_date="2025-07-15" if past.startswith("2025") else "2023-07-15", timezone="UTC"))
        seas[f"archive/{past}"] = dict(status=st, detail=(str(doc)[:150] if st != 200 else "ok"))
        time.sleep(3)
    res["seasonal"] = seas
    # 5. Ensemble API variable coverage (WeatherNext 2, GEFS, IFS) for the logger's levels
    ens = {}
    for model in ("gfs_seamless", "gfs025", "ecmwf_ifs025", "google_weathernext2_ensemble", "ecmwf_aifs025_ensemble"):
        st, doc = get("https://ensemble-api.open-meteo.com/v1/ensemble", dict(hourly="temperature_500hPa,temperature_2m", models=model, forecast_days=16, timezone="UTC"))
        ens[model] = dict(status=st, members=sum(k.startswith("temperature_500hPa") for k in doc.get("hourly", {})) if st == 200 else None,
                          hours=len(doc.get("hourly", {}).get("time", [])) if st == 200 else str(doc)[:100])
        time.sleep(3)
    res["ensemble"] = ens
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1)[:12000])


if __name__ == "__main__":
    main()
