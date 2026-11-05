"""Health report: counts, gaps and staleness from a synthetic archive."""
import gzip
import os
from datetime import datetime, timedelta, timezone

from tempest.ops import health


def _touch(root, site, source, names):
    d = os.path.join(root, "raw", site, source)
    os.makedirs(d, exist_ok=True)
    for n in names:
        with gzip.open(os.path.join(d, n + ".json.gz"), "wb") as f:
            f.write(b"{}")


def test_gap_and_staleness_are_detected(tmp_path):
    now = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)
    fmt = lambda t: t.strftime("%Y%m%d_%Hz")
    slots = [now.replace(hour=0) - timedelta(hours=12 * k) for k in range(8)]
    _touch(str(tmp_path), "a", "ecmwf_ifs025", [fmt(s) for s in slots])                          # complete, fresh
    _touch(str(tmp_path), "b", "ecmwf_ifs025", [fmt(s) for k, s in enumerate(slots) if k != 2])   # one slot missing 1.5 days ago
    _touch(str(tmp_path), "c", "ecmwf_ifs025", [fmt(slots[5]), fmt(slots[6])])                     # newest is 2.5 days old
    rep = health.scan(str(tmp_path), now)
    assert not rep["a/ecmwf_ifs025"]["stale"] and not rep["a/ecmwf_ifs025"]["recent_gap"] and rep["a/ecmwf_ifs025"]["missing_slots_14d"] == []
    assert rep["b/ecmwf_ifs025"]["recent_gap"] and len(rep["b/ecmwf_ifs025"]["missing_slots_14d"]) == 1
    assert rep["c/ecmwf_ifs025"]["stale"]


def test_assets_check_flags_a_changed_file(tmp_path):
    import hashlib
    import json
    (tmp_path / "x.npz").write_bytes(b"abc")
    json.dump({"files": {"x.npz": hashlib.sha256(b"abc").hexdigest()}, "created": "t", "model_source": "m"}, open(tmp_path / "manifest.json", "w"))
    assert health.assets_check(str(tmp_path))["problems"] == []
    (tmp_path / "x.npz").write_bytes(b"abd")
    assert health.assets_check(str(tmp_path))["problems"] == ["x.npz: hash differs"]
