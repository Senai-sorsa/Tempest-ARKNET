"""Runs in the simulator's venv: import once, then run one worker script per stdin line, so flights share the import cost.
A job is JSON {"script", "argv", "cwd"}; each reply is one JSON line, {"error": traceback or null}.
The workers patch classes at runtime, so those are put back before every job, or one flight's model would leak into the next."""
import json
import os
import runpy
import sys
import traceback
from pathlib import Path

import numpy  # noqa: F401
import pandas  # noqa: F401
from flight_sim.simulation import Simulation  # noqa: F401
from flight_sim.vehicle.engine import SolidEngine
from flight_sim.vehicle.reynolds_correction import ReynoldsCorrection

sys.path.append(str(Path(__file__).parent))  # for sim.toml's profile_air, appended as in profile_worker.py
ORIGINALS = (SolidEngine, "get_thrust", SolidEngine.get_thrust), (ReynoldsCorrection, "__call__", ReynoldsCorrection.__call__)
replies, sys.stdout = sys.stdout, sys.stderr  # a stray print must not pass for a reply

for line in sys.stdin:
    job = json.loads(line)
    for owner, name, original in ORIGINALS:
        setattr(owner, name, original)
    try:
        os.chdir(job["cwd"])
        sys.argv = job["argv"]
        runpy.run_path(job["script"], run_name="__main__")
        error = None
    except (Exception, SystemExit):
        error = traceback.format_exc()
    replies.write(json.dumps({"error": error}) + "\n")
    replies.flush()
