"""Streams chosen pNEUMA members to compact 5 Hz arrays. Held-out drones and days are refused and never downloaded.
python3 -I pneuma_fetch.py d1:20181024:0830 ...  Output: cars-data/truth/junction-25/pneuma/<member>.npz"""
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from common import OUT
import remotezip

URL = 'https://zenodo.org/api/records/10491409/files/pNEUMA_dataset.zip/content'
LAT0, LON0 = 37.98, 23.735
HELD_D, HELD_DAY = {'d3', 'd6', 'd8'}, {'20181029'}
CLS = {'Car': 0, 'Taxi': 1, 'Bus': 2, 'Medium Vehicle': 3, 'Heavy Vehicle': 4, 'Motorcycle': 5}
P = OUT / 'pneuma'
P.mkdir(exist_ok=True)


def one(z, name, out):
    I, C, T, X, Y, V = [], [], [], [], [], []
    with z.open(name) as f:
        t = io.TextIOWrapper(f, encoding='ascii', errors='ignore', newline='\n')
        next(t)
        for line in t:
            a = line.split(';', 4)
            if len(a) < 5:
                continue
            c = CLS.get(a[1].strip(), 6)
            v = np.fromstring(a[4], sep=';')
            n = len(v) // 6
            if n < 5:
                continue
            v = v[:n * 6].reshape(n, 6)[::5]
            I.append(np.full(len(v), int(a[0]), 'i4'))
            C.append(np.full(len(v), c, 'i1'))
            T.append(v[:, 5].astype('f4'))
            X.append(((v[:, 1] - LON0) * 111320 * np.cos(np.deg2rad(LAT0))).astype('f4'))
            Y.append(((v[:, 0] - LAT0) * 110574).astype('f4'))
            V.append((v[:, 2] / 3.6).astype('f4'))
    np.savez_compressed(out, id=np.concatenate(I), cls=np.concatenate(C), t=np.concatenate(T), x=np.concatenate(X), y=np.concatenate(Y), v=np.concatenate(V))
    print(name, 'tracks', len(I), 'rows', sum(map(len, I)), flush=True)


def main(args):
    z = remotezip.open_zip(URL)
    names = {i.filename.split('/')[-1]: i.filename for i in z.infolist()}
    for a in args:
        d, day, w = a.split(':')
        if d in HELD_D or day in HELD_DAY:
            raise SystemExit(f'{a} is held out')
        m = [k for k in names if k.startswith(f'{day}_{d}_{w}')]
        if not m:
            print('missing', a, flush=True)
            continue
        out = P / (m[0][:-4] + '.npz')
        if out.exists():
            continue
        one(z, names[m[0]], out)


if __name__ == '__main__':
    main(sys.argv[1:])
