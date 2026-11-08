"""N1-N3 and I1-I3: retries, backoff, rate limits, offline mode, resumable download, atomic writes, self-healing cache. No real network."""
import io
import os
import urllib.error

import pytest

from tempest_weather_v2 import _files, _net


class Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, headers=None):
    return urllib.error.HTTPError("http://x", code, "err", headers or {}, None)


class Opener:
    """Scripted responses: each item is bytes (success) or an exception to raise."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return Resp(item)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))
    monkeypatch.delenv("TEMPEST_OFFLINE", raising=False)
    _net.set_offline(None)
    _net._last_call.clear()


def run(script, **kw):
    sleeps = []
    op = Opener(script)
    return op, sleeps, lambda: _net.fetch("http://x", opener=op, sleep=sleeps.append, **kw)


def test_retries_5xx_and_network_errors_with_backoff_then_succeeds():
    op, sleeps, call = run([http_error(503), urllib.error.URLError("reset"), b"ok"])
    assert call() == b"ok" and op.calls == 3
    assert 0.74 <= sleeps[0] <= 1.26 and 1.49 <= sleeps[1] <= 2.51          # 1 s and 2 s, +-25 % jitter


def test_429_honours_retry_after_and_4xx_is_not_retried():
    op, sleeps, call = run([http_error(429, {"Retry-After": "7"}), b"ok"])
    assert call() == b"ok" and sleeps == [7.0]
    op, sleeps, call = run([http_error(404), b"never"])
    with pytest.raises(_net.NetError, match="404"):
        call()
    assert op.calls == 1 and sleeps == []


def test_gives_up_after_three_retries():
    op, sleeps, call = run([http_error(500)] * 4)
    with pytest.raises(_net.NetError, match="4 attempts"):
        call()
    assert op.calls == 4 and len(sleeps) == 3


def test_offline_blocks_before_any_request(monkeypatch):
    op = Opener([b"x"])
    _net.set_offline(True)
    with pytest.raises(_net.OfflineError):
        _net.fetch("http://x", opener=op)
    assert op.calls == 0
    _net.set_offline(None)
    monkeypatch.setenv("TEMPEST_OFFLINE", "1")
    with pytest.raises(_net.OfflineError):
        _net.fetch("http://x", opener=op)
    assert op.calls == 0


def test_rate_limit_spaces_calls_and_daily_cap():
    clock = [100.0]
    sleeps = []
    op = Opener([b"a", b"b"])
    _net.fetch("http://x", service="iem", opener=op, sleep=sleeps.append, clock=lambda: clock[0])
    clock[0] += 0.3
    _net.fetch("http://x", service="iem", opener=op, sleep=sleeps.append, clock=lambda: clock[0])
    assert sleeps and abs(sleeps[0] - 0.7) < 1e-9                              # 1 s minimum gap, 0.3 s already passed
    old = _net.RATE_LIMITS["opentopodata"]
    _net.RATE_LIMITS["opentopodata"] = (0.0, 2)
    try:
        op = Opener([b"1", b"2", b"3"])
        _net.fetch("http://x", service="opentopodata", opener=op, sleep=lambda s: None)
        _net.fetch("http://x", service="opentopodata", opener=op, sleep=lambda s: None)
        with pytest.raises(_net.NetError, match="daily limit"):
            _net.fetch("http://x", service="opentopodata", opener=op, sleep=lambda s: None)
    finally:
        _net.RATE_LIMITS["opentopodata"] = old


def test_fetch_json_error_is_a_neterror():
    op = Opener([b"not json"])
    with pytest.raises(_net.NetError, match="JSON"):
        _net.fetch_json("http://x", opener=op)


def test_resumable_download_continues_from_the_partial_file(tmp_path):
    dest = str(tmp_path / "big.bin")
    with open(dest + ".partial", "wb") as f:
        f.write(b"0123")

    class R206(Resp):
        status = 206

    seen = {}

    def opener(req, timeout=None):
        seen["range"] = req.headers.get("Range")
        return R206(b"456789")

    _net.download_resumable("http://x", dest, opener=opener, sha256=_files.sha256_bytes(b"0123456789"))
    assert seen["range"] == "bytes=4-" and open(dest, "rb").read() == b"0123456789" and not os.path.exists(dest + ".partial")
    # a server that ignores Range sends everything: start over
    with open(dest + ".partial", "wb") as f:
        f.write(b"zz")
    _net.download_resumable("http://x", dest, opener=lambda req, timeout=None: Resp(b"abc"))
    assert open(dest, "rb").read() == b"abc"
    with pytest.raises(_net.NetError, match="checksum"):
        _net.download_resumable("http://x", dest + "2", opener=lambda req, timeout=None: Resp(b"abc"), sha256="0" * 64)
    assert not os.path.exists(dest + "2")


def test_atomic_write_leaves_no_temp_file_and_replaces_whole(tmp_path):
    p = str(tmp_path / "a" / "f.txt")
    _files.atomic_write(p, "one")
    _files.atomic_write(p, b"two")
    assert open(p, "rb").read() == b"two"
    assert [n for n in os.listdir(os.path.dirname(p)) if ".tmp." in n] == []


def test_cache_self_heals_when_corrupt_or_truncated(tmp_path):
    p = str(tmp_path / "c.bin")
    _files.cache_put(p, b"hello world")
    assert _files.cache_get(p) == b"hello world"
    with open(p, "wb") as f:                      # corrupt the data, keep the checksum
        f.write(b"hello wor")
    assert _files.cache_get(p) is None and not os.path.exists(p) and not os.path.exists(p + ".sha256")
    assert _files.cache_get(str(tmp_path / "missing")) is None


def test_read_json_deletes_a_corrupt_file_and_lock_is_exclusive(tmp_path):
    p = str(tmp_path / "j.json")
    with open(p, "w") as f:
        f.write("{broken")
    assert _files.read_json(p, {"d": 1}) == {"d": 1} and not os.path.exists(p)
    _files.atomic_json(p, {"a": 1})
    assert _files.read_json(p) == {"a": 1}
    with _files.file_lock(p):
        with pytest.raises(TimeoutError):
            with _files.file_lock(p, timeout=0.2, poll=0.02):
                pass
    with _files.file_lock(p, timeout=0.5):        # released again
        pass
