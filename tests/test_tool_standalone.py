"""The tool folder runs with numpy only: pandas, torch and xarray are blocked, the package is imported from a copy outside the repo."""
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

ASSETS = os.path.abspath("tempest_weather/assets")
needs_assets = pytest.mark.skipif(not os.path.exists(os.path.join(ASSETS, "manifest.json")), reason="assets not exported")


@needs_assets
def test_runs_in_a_scratch_folder_with_only_numpy(tmp_path):
    shutil.copytree("tempest_weather", tmp_path / "tempest_weather", ignore=shutil.ignore_patterns("assets", "__pycache__"))
    code = textwrap.dedent(f"""
        import sys
        for m in ("pandas", "torch", "xarray", "scipy", "tempest"):
            sys.modules[m] = None                      # importing any of these now raises ImportError
        sys.path.insert(0, r"{tmp_path}")
        import tempest_weather as tw
        from tempest_weather import api
        r = tw.values(32.99, -106.97, "2027-06-16 15:00", ["t2m_c", "wind_speed@100"], n=199, assets=r"{ASSETS}")
        d = tw.distribution(32.99, -106.97, "2027-06-16 15:00", ["t2m_c"], setting=0, n=199, assets=r"{ASSETS}")
        a = tw.atmosphere(32.99, -106.97, "2027-06-16 15:00", (15, 85), n=199, assets=r"{ASSETS}")
        assert 20 < r["values"]["t2m_c"] < 50 and d["variables"]["t2m_c"]["type"] in ("normal", "empirical", "gumbel")
        assert a[0]["meta"]["flight_score"] > a[1]["meta"]["flight_score"]
        print("OK", sorted(m for m in sys.modules if m.split(".")[0] in ("pandas", "torch", "xarray") and sys.modules[m] is not None))
    """)
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=600, cwd=str(tmp_path))
    assert r.returncode == 0 and r.stdout.strip().startswith("OK []"), r.stderr[-1500:]
