"""The long-lived FS process keeps running after a bad job and hands each job the unpatched classes."""
import pytest

from fsval import fsrun


def test_server_survives_a_failure_and_resets_patches(tmp_path):
    patch = tmp_path / "patch.py"
    patch.write_text("from flight_sim.vehicle.reynolds_correction import ReynoldsCorrection\nReynoldsCorrection.__call__ = None\nraise ValueError('bad flight')\n")
    check = tmp_path / "check.py"
    check.write_text("import os, sys\nfrom flight_sim.vehicle.reynolds_correction import ReynoldsCorrection\n"
                     "assert ReynoldsCorrection.__call__ is not None\nassert sys.argv[1] == 'x'\nopen('done', 'w').write(os.getcwd())\n")
    with pytest.raises(RuntimeError, match="bad flight"):
        fsrun._run(str(patch), [], tmp_path)
    fsrun._run(str(check), ["x"], tmp_path)
    assert (tmp_path / "done").exists()
