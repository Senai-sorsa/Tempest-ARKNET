"""New_Plan 17.4 helper: where the three "change now" defaults stand, and what each held item still waits for. Read-only (changes nothing).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/change_now_status.py
Each "change now" row prints the current default, the one edit that flips it, and the checks to run after the edit (17.4: backup, full suite at
16 threads, scripts/tool_audit.py, scripts/shipped_check.py, golden hashes in tests/test_flags_off.py if they move). Flipping needs the user's go.
"""
import inspect
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(REPO, "docs", "results", "logs")


def fair_baseline_default():
    out = []
    for f in ("tempest/scoring/score.py", "tempest/scoring/sonde.py"):
        with open(os.path.join(REPO, f), encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r'add_argument\("--fair-baseline", action="store_true"(, default=(\w+))?', src)
        out.append((f, "off" if m and not m.group(1) else (m.group(2) if m else "flag not found")))
    return out


def last_verdict(log):
    p = os.path.join(LOGS, f"kit_{log}.log")
    if not os.path.exists(p):
        return "not run"
    with open(p, encoding="utf-8") as fh:
        v = [ln.strip() for ln in fh if "erdict" in ln or "Reading" in ln]
    return v[-1][:160] if v else "run, no verdict line"


def main():
    from tempest_weather.flight.engine import TempestFlightSimEngine
    from tempest_weather_v2.launch import Launch
    print("CHANGE NOW (New_Plan 17.4; each needs the user's go when it is done)")
    for f, state in fair_baseline_default():
        print(f"  1. fair baseline in {f}: default {state}. Flip: add default=True to the --fair-baseline add_argument (and a --plain-baseline flag to switch back);"
              " then rewrite the README headline (ERA5 skill15 about +1.7 to +1.8 %, AU-1 step 5). No tool output changes.")
    t_up = inspect.signature(Launch.observe).parameters["t_update"].default
    print(f"  2. Student-t widening for ground reports: Launch.observe(t_update=...) default {t_up}. Flip: t_update=True in the signature of "
          "tempest_weather_v2/launch.py Launch.observe (observe_radar stays False until UR10).")
    z0 = inspect.signature(TempestFlightSimEngine.sample_sobol_batch).parameters["z0_roughness_m"].default
    print(f"  3. site roughness for turbulence: sample_sobol_batch(z0_roughness_m=...) default {z0!r}. Flip for Launch engines only: make Launch.engine() "
          "pass z0 'site' (e.g. store info['z0_default'] = 'site' and use it when the caller gives none); other engines keep 0.03.")
    print("HOLD (New_Plan 17.4): what each waits for, with the latest verdict line on file")
    for item, log in (("SIGMA days 8-10", "b24_ur7_sigma_cov"), ("SIGMA / NEST tails", "b25_ur1_tailcal"), ("world start (AV29) -> UR2 stage 3", "b26_ur2_stack"),
                      ("N1 cross-fit -> UR8", "b31_ur8_control"), ("real-air gap -> UR3 (b)", "b27_ur3_gridpoint"), ("IL-207b -> UR9", "b32_ur9_il207b_seed2"),
                      ("radar t-update -> UR10", "b33_ur10_radar_t"), ("older-run mix -> UR13 / UR15", "b37_ur15_third_period"), ("two neighbours -> UR14", "b36_ur14_obs_stack")):
        print(f"  {item:<36} {last_verdict(log)}")


if __name__ == "__main__":
    main()
