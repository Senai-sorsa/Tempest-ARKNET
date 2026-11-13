"""AU-13 (New_Plan 15.3): read_igra can drop soundings launched away from the listed launch height (opt-in; default keeps all)."""
import zipfile

import numpy as np

from tempest.calibrate.station import read_igra


def _sounding(year, gph0):
    head = f"#USM00072364 {year:04d} 06 01 12 1100{3:5d}".ljust(80)
    assert int(head[13:17]) == year and int(head[24:26]) == 12 and int(head[31:36]) == 3
    rows = []
    for k, (p, dz, t) in enumerate(((87000, 0, 3000), (85000, 200, 2990), (70000, 1700, 2850))):
        f = [-99999] * 17
        f[0], f[2], f[3], f[12], f[14], f[16] = p, gph0 + dz, t, 400, 50, -20
        rows.append(" ".join(f"{x:7d}" for x in f))
    return [head] + rows


def test_two_soundings_one_launched_60m_away(tmp_path, capsys):
    path = tmp_path / "USM00072364-drvd.txt.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("USM00072364-drvd.txt", "\n".join(_sounding(1993, 1314) + _sounding(2015, 1254)) + "\n")
    t_all, prof_all, _ = read_igra(str(path), 1991, 2020)
    assert len(t_all) == 2 and "dropped" not in capsys.readouterr().out          # default: unchanged, no count line
    t, prof, sfc = read_igra(str(path), 1991, 2020, launch_height=1254.0, tol_m=30)
    assert len(t) == 1 and t[0].year == 2015 and np.array_equal(prof[0], prof_all[1], equal_nan=True)
    assert "1 soundings dropped" in capsys.readouterr().out
