"""Runs in the simulator's venv: make profile_air importable for sim.toml, then run the surface worker.
Appended, not prepended: this folder has modules whose names could shadow installed ones."""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.append(str(HERE))
runpy.run_path(str(HERE / "surface_worker.py"), run_name="__main__")
