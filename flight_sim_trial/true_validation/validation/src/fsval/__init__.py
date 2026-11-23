"""Validation harness. Reads the simulator only through its own venv's processes; never edits it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # validation/
FS_REPO = ROOT.parent
FS_PYTHON = FS_REPO / ".venv" / "Scripts" / "python.exe"
RPA = Path.home() / "Rocket-Profile-Analysis"  # user's local clone, never committed here
RAS_VENDOR = RPA / "vendor" / "rasaero"
RAS_HOST = RPA / "native" / "RasaeroHost" / "bin" / "Release" / "net8.0" / "rasaero-host.dll"
