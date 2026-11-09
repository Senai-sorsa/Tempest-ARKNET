"""A read-only file object over HTTP range requests (stdlib urllib) with a block cache, so h5py can open a huge remote HDF5 file and read only the chunks it needs. Counts the bytes fetched."""
import io
import urllib.request


class RangeFile(io.RawIOBase):
    def __init__(self, url, block=4 * 1024 * 1024, ua="tempest-research"):
        self.url, self.block, self.ua = url, block, ua
        r = urllib.request.Request(url, method="HEAD", headers={"User-Agent": ua})
        self.size = int(urllib.request.urlopen(r, timeout=60).headers["Content-Length"])
        self.pos = 0
        self.cache = {}
        self.fetched = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _blk(self, i):
        if i not in self.cache:
            a, b = i * self.block, min((i + 1) * self.block, self.size) - 1
            r = urllib.request.Request(self.url, headers={"User-Agent": self.ua, "Range": f"bytes={a}-{b}"})
            for attempt in range(3):
                try:
                    data = urllib.request.urlopen(r, timeout=120).read()
                    break
                except Exception:   # noqa: BLE001
                    if attempt == 2:
                        raise
            self.fetched += len(data)
            self.cache[i] = data
            if len(self.cache) > 64:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[i]

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        out, p = bytearray(), self.pos
        while len(out) < n:
            i = p // self.block
            blk = self._blk(i)
            off = p - i * self.block
            take = min(n - len(out), len(blk) - off)
            out += blk[off:off + take]
            p += take
        buf[:n] = out
        self.pos += n
        return n
