"""Read members of a remote zip with HTTP ranges, so that held-out members are never downloaded."""
import io
import urllib.request
import zipfile

CHUNK = 8 << 20


class Remote(io.RawIOBase):
    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60)
        self.url, self.n, self.p = r.url, int(r.headers['Content-Length']), 0
        self.b0, self.buf = 0, b''

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.p

    def seek(self, o, w=0):
        self.p = {0: o, 1: self.p + o, 2: self.n + o}[w]
        return self.p

    def read(self, k=-1):
        if k < 0:
            k = self.n - self.p
        if k == 0 or self.p >= self.n:
            return b''
        if not (self.b0 <= self.p and self.p + k <= self.b0 + len(self.buf)):
            end = min(self.p + max(k, CHUNK), self.n) - 1
            q = urllib.request.Request(self.url, headers={'Range': f'bytes={self.p}-{end}'})
            for attempt in range(4):
                try:
                    self.buf = urllib.request.urlopen(q, timeout=300).read()
                    break
                except OSError:
                    if attempt == 3:
                        raise
            self.b0 = self.p
        i = self.p - self.b0
        out = self.buf[i:i + k]
        self.p += len(out)
        return out


def open_zip(url):
    return zipfile.ZipFile(Remote(url))
