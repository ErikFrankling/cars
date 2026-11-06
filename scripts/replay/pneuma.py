"""pNEUMA (Athens, 4 weekday mornings, 10 drones): streaming reader, inventory, lanes from trajectory density,
signal reading, T3 replay scene. research/truth/replay/PNEUMA.md says what each step found.

The zip (15 GB, 98 GB unpacked) is never unpacked: each per-drone file is streamed row by row from the zip, resampled
to 5 Hz on a common 0.2 s grid and written to cars-data/replay/pneuma/raw/<day>_d<k>_<hhmm>.npz in metres (UTM 34N
minus a fixed origin). The dX files (all drones merged) are not read: the per-drone files hold the same tracks.

    python3 -I scripts/replay/pneuma.py convert [GLOB]     # long: run as agent-job
    python3 -I scripts/replay/pneuma.py inventory           # -> research/truth/replay/pneuma_inventory.json
"""
import os, sys, io, re, json, zipfile, glob, fnmatch
import numpy as np

ZIP = '/home/erikf/projects/personal/cars-data/datasets/pneuma-full/pNEUMA_dataset.zip'
OUTD = '/home/erikf/projects/personal/cars-data/replay/pneuma'
RAW = os.path.join(OUTD, 'raw')
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
TYPES = ['Car', 'Taxi', 'Bus', 'Medium Vehicle', 'Heavy Vehicle', 'Motorcycle']
DIMS = {0: (5.0, 2.0), 1: (5.0, 2.0), 2: (12.5, 4.0), 3: (5.83, 2.67), 4: (12.5, 3.33), 5: (2.5, 1.0)}
ORIGIN = (738000.0, 4206000.0)          # UTM 34N easting, northing subtracted (Athens centre is near 739.5k, 4207k)
DT = 0.2
NAME = re.compile(r'(\d{8})_d(\d+)_(\d{4})_(\d{4})\.csv$')


def proj():
    import pyproj
    return pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32634', always_xy=True)


def to_xy(tr, lat, lon):
    x, y = tr.transform(lon, lat)
    return np.asarray(x) - ORIGIN[0], np.asarray(y) - ORIGIN[1]


def convert_one(z, name, tr):
    m = NAME.search(name)
    day, drone, hhmm = m[1], int(m[2]), m[3]
    t_start = int(hhmm[:2]) * 3600 + int(hhmm[2:]) * 60
    out = os.path.join(RAW, f'{day}_d{drone}_{hhmm}.npz')
    if os.path.exists(out):
        return
    ids, typ, off, dist = [], [], [0], []
    T, LA, LO, V, AX, AY = [], [], [], [], [], []
    with z.open(name) as fb:
        f = io.TextIOWrapper(fb, encoding='utf-8', errors='replace')
        f.readline()
        for line in f:
            p = line.split(';', 4)
            if len(p) < 5:
                continue
            a = np.array([s for s in p[4].replace('\n', '').split(';') if s.strip()], dtype=float)
            a = a[:len(a) // 6 * 6].reshape(-1, 6)
            if len(a) < 2:
                continue
            t = a[:, 5]
            g = np.arange(np.ceil(t[0] / DT - 1e-6), np.floor(t[-1] / DT + 1e-6) + 1) * DT
            if len(g) < 1:
                continue
            ids.append(int(p[0])); typ.append(TYPES.index(p[1].strip())); dist.append(float(p[2]))
            T.append(g.astype(np.float32))
            for dst, c in ((LA, 0), (LO, 1), (V, 2), (AX, 3), (AY, 4)):
                dst.append(np.interp(g, t, a[:, c]))
            off.append(off[-1] + len(g))
    la = np.concatenate(LA); lo = np.concatenate(LO)
    x, y = to_xy(tr, la, lo)
    np.savez(out + '.tmp.npz', id=np.array(ids, np.int32), type=np.array(typ, np.uint8), off=np.array(off, np.int64),
             dist=np.array(dist, np.float32), t0=np.float64(t_start), t=np.concatenate(T), x=x.astype(np.float32), y=y.astype(np.float32),
             v=(np.concatenate(V) / 3.6).astype(np.float32), ax=np.concatenate(AX).astype(np.float32), ay=np.concatenate(AY).astype(np.float32))
    os.replace(out + '.tmp.npz', out)
    print(name, len(ids), off[-1], flush=True)


def convert(pat='*'):
    os.makedirs(RAW, exist_ok=True)
    tr = proj()
    z = zipfile.ZipFile(ZIP)
    names = [i.filename for i in z.infolist() if NAME.search(i.filename) and fnmatch.fnmatch(os.path.basename(i.filename), pat)]
    for n in sorted(names, key=lambda s: (NAME.search(s)[2].zfill(2), s)):
        convert_one(z, n, tr)


def load(day, drone, hhmm):
    d = np.load(os.path.join(RAW, f'{day}_d{drone}_{hhmm}.npz'))
    return {k: d[k] for k in d.files}


def files():
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.npz'))):
        m = re.search(r'(\d{8})_d(\d+)_(\d{4})\.npz$', p)
        if m:
            out.append((m[1], int(m[2]), m[3], p))
    return out


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'convert':
        convert(sys.argv[2] if len(sys.argv) > 2 else '*')
