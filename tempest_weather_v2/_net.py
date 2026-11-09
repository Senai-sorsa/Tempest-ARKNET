"""Shared single-thread network layer (spec N1-N3). Every network call in v2 goes through ``fetch``. Stdlib only, no threads, no processes.

* timeouts: connect 5 s, read 15 s (urllib has one timeout, so the larger read value is used for the socket and the connect budget is checked by the caller's retry loop);
* up to 3 retries with exponential backoff and +-25 % jitter (1, 2, 4 s) on network errors, HTTP 429 (honouring Retry-After) and HTTP 5xx; never retries other 4xx;
* per-service rate limits (minimum interval between calls, optional daily cap kept in the user cache with a cross-process lock);
* strict offline mode (``set_offline(True)``, env ``TEMPEST_OFFLINE=1``): raises ``OfflineError`` before any socket is created, so callers fall back to cached or bundled data;
* ``download_resumable`` fetches large files with HTTP Range into ``<dest>.partial``; Ctrl+C leaves the partial file, rerunning resumes.

The hooks ``opener``, ``sleep`` and ``clock`` are injectable so everything is testable without a network.
"""
import json
import os
import random
import time
import urllib.error
import urllib.request

from tempest_weather_v2 import _files

__all__ = ["NetError", "OfflineError", "set_offline", "is_offline", "fetch", "fetch_json", "download_resumable", "RATE_LIMITS"]

CONNECT_TIMEOUT, READ_TIMEOUT, RETRIES, BACKOFF = 5.0, 15.0, 3, (1.0, 2.0, 4.0)
# service -> (minimum seconds between calls, calls per day or None)
RATE_LIMITS = {"opentopodata": (1.0, 1000), "aviationweather": (1.0, None), "iem": (1.0, None), "usgs-epqs": (0.2, None), "open-meteo": (0.2, None)}
USER_AGENT = "tempest-weather/2 (+https://github.com/Senai-sorsa/Tempest-ARKNET)"

_offline = None          # None = look at the environment
_last_call = {}          # service -> monotonic time of the last call (this process)


class NetError(Exception):
    """A request failed for good (retries used up, or a non-retryable HTTP status)."""


class OfflineError(NetError):
    """Offline mode is on: no socket was opened."""


def set_offline(flag):
    global _offline
    _offline = None if flag is None else bool(flag)


def is_offline():
    if _offline is not None:
        return _offline
    return os.environ.get("TEMPEST_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def _rate_limit(service, sleep, clock):
    if service not in RATE_LIMITS:
        return
    gap, per_day = RATE_LIMITS[service]
    wait = gap - (clock() - _last_call.get(service, -1e9))
    if wait > 0:
        sleep(wait)
    if per_day:
        path = os.path.join(_files.cache_dir("net"), f"quota_{service}.json")
        today = time.strftime("%Y-%m-%d", time.gmtime())
        with _files.file_lock(path):
            q = _files.read_json(path, {}) or {}
            if q.get("day") != today:
                q = {"day": today, "n": 0}
            if q["n"] >= per_day:
                raise NetError(f"{service}: daily limit of {per_day} calls reached")
            q["n"] += 1
            _files.atomic_json(path, q)
    _last_call[service] = clock()


def _backoff(attempt, retry_after, rng):
    if retry_after is not None:
        return retry_after
    base = BACKOFF[min(attempt, len(BACKOFF) - 1)]
    return base * (1.0 + 0.25 * (2.0 * rng.random() - 1.0))


def fetch(url, *, service=None, headers=None, timeout=None, retries=RETRIES, data=None, opener=None, sleep=time.sleep, clock=time.monotonic, rng=random):
    """GET (or POST with `data`) -> bytes. See the module docstring for the retry, rate-limit and offline rules."""
    if is_offline():
        raise OfflineError(f"offline mode: not fetching {url}")
    opener = opener or urllib.request.urlopen
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    last = None
    for attempt in range(retries + 1):
        _rate_limit(service, sleep, clock)
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with opener(req, timeout=timeout or READ_TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                ra = e.headers.get("Retry-After") if e.headers else None
                last = e
                retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
            else:
                raise NetError(f"HTTP {e.code} for {url}") from e         # other 4xx: never retried
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last, retry_after = e, None
        if attempt < retries:
            sleep(_backoff(attempt, retry_after if isinstance(last, urllib.error.HTTPError) else None, rng))
    raise NetError(f"{url} failed after {retries + 1} attempts: {last}")


def fetch_json(url, **kw):
    try:
        return json.loads(fetch(url, **kw).decode("utf-8"))
    except ValueError as e:
        raise NetError(f"{url} did not return JSON: {e}") from e


def download_resumable(url, dest, *, sha256=None, chunk=1 << 20, opener=None, **kw):
    """Download to `dest` through `<dest>.partial`, resuming with an HTTP Range request. Verifies `sha256` when given (a mismatch deletes the file and raises)."""
    if is_offline():
        raise OfflineError(f"offline mode: not downloading {url}")
    opener = opener or urllib.request.urlopen
    part = dest + ".partial"
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **({"Range": f"bytes={have}-"} if have else {})})
    try:
        with opener(req, timeout=READ_TIMEOUT) as resp:
            status = getattr(resp, "status", 200)
            mode = "ab" if have and status == 206 else "wb"     # a server that ignores Range sends the whole file: start over
            with open(part, mode) as f:
                while True:
                    block = resp.read(chunk)
                    if not block:
                        break
                    f.write(block)
                f.flush()
                os.fsync(f.fileno())
    except urllib.error.HTTPError as e:
        if e.code == 416 and have:        # range not satisfiable: the partial file is already complete
            pass
        else:
            raise NetError(f"HTTP {e.code} for {url}") from e
    if sha256 and _files.sha256_file(part) != sha256:
        os.remove(part)
        raise NetError(f"checksum mismatch for {url}")
    os.replace(part, dest)
    return dest
