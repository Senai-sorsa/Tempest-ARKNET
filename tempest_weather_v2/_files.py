"""File safety (spec I1-I3): atomic writes, self-healing checked cache, cross-process lock, SHA-256 helpers. Stdlib only.

* every write goes to ``<path>.tmp.<pid>``, is fsync'd and moved with ``os.replace``: no half-written file ever has its final name and parallel processes never share a temp name;
* ``cache_put`` / ``cache_get`` store a SHA-256 next to the data; a corrupt or truncated entry is deleted and reported as a miss, so the caller simply refetches;
* ``file_lock`` is a small cross-process lock (``msvcrt`` on Windows, ``fcntl`` elsewhere) for shared JSON caches.
"""
import contextlib
import hashlib
import json
import os
import time

__all__ = ["cache_dir", "atomic_write", "atomic_json", "read_json", "sha256_bytes", "sha256_file", "cache_put", "cache_get", "file_lock"]


def cache_dir(sub=""):
    """User cache folder (TEMPEST_CACHE, else %LOCALAPPDATA%\\tempest on Windows, ~/.cache/tempest elsewhere); created on demand."""
    base = os.environ.get("TEMPEST_CACHE")
    if not base:
        root = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.path.join(os.path.expanduser("~"), ".cache")
        base = os.path.join(root or os.path.expanduser("~"), "tempest")
    path = os.path.join(base, sub) if sub else base
    os.makedirs(path, exist_ok=True)
    return path


def atomic_write(path, data):
    """Write bytes (or str, as UTF-8) so that `path` is either the old content or the complete new content, never a partial file."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            with contextlib.suppress(OSError):
                os.remove(tmp)


def atomic_json(path, obj):
    atomic_write(path, json.dumps(obj, indent=1, sort_keys=True))


def read_json(path, default=None):
    """JSON file -> object; a missing file gives `default`, a corrupt one is deleted (self-healing) and also gives `default`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (ValueError, OSError):
        with contextlib.suppress(OSError):
            os.remove(path)
        return default


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def cache_put(path, data):
    """Store bytes with their SHA-256 (`<path>` and `<path>.sha256`). The checksum is written last, so a crash in between reads as a miss."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    atomic_write(path, data)
    atomic_write(path + ".sha256", sha256_bytes(data))


def cache_get(path):
    """Bytes stored by `cache_put`, or None when missing or corrupt (corrupt entries are removed so the next call refetches)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        with open(path + ".sha256", "r", encoding="utf-8") as f:
            want = f.read().strip()
    except OSError:
        return None
    if sha256_bytes(data) != want:
        for p in (path, path + ".sha256"):
            with contextlib.suppress(OSError):
                os.remove(p)
        return None
    return data


@contextlib.contextmanager
def file_lock(path, timeout=10.0, poll=0.05):
    """Cross-process exclusive lock on `<path>.lock`; raises TimeoutError after `timeout` seconds. Use around read-modify-write of a shared cache file."""
    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    f = open(lock_path, "a+b")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"could not lock {lock_path} within {timeout} s")
                time.sleep(poll)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                with contextlib.suppress(OSError):
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                with contextlib.suppress(OSError):
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()
