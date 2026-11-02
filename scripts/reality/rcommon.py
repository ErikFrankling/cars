"""Shared loaders for rung 1. Locked sites are dropped here, before anything reads them. Run with python3 -I."""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path('/home/erikf/projects/personal/cars-data')
B19 = DATA / 'berlin2019'
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'research/truth/berlin2019'
FREEZE = json.load(open(B19 / 'step1/freeze.json'))
DAYS = FREEZE['tuning_days']
LOCKED = set(FREEZE['locked_sites_all_berlin'])
DISTRICT_TUNING = set(FREEZE['tuning_sites'])
BOX = FREEZE['district']['box']
UNSPLIT = {'TE002'}  # the only unlocked motorway station; quality weak, not on any tuning list. Kept apart.
JAM_FRACTION = 0.7  # metrics.py


def sites():
    s = pd.read_csv(B19 / 'step0/sites.csv')
    s = s[~s.site.isin(LOCKED)]
    s = s[(s.quality == 'trusted') | s.site.isin(UNSPLIT)].copy()
    s['scope'] = np.where(s.site.isin(DISTRICT_TUNING), 'district', np.where(s.site.isin(UNSPLIT), 'unsplit', 'berlin'))
    return s


def loops():
    """Station-hours, tuning days, faulty site-days out, allowed sites only."""
    keep = set(sites().site)
    d = pd.read_csv(B19 / 'step1/real_days.csv.gz')
    d = d[d.site.isin(keep) & d.date.isin(DAYS)].copy()
    return d


def unsplit_loops():
    """TE002 is not in real_days (or may not be): read it alone from the raw station file."""
    raw = pd.read_csv(DATA / 'datasets/berlin-2019-detectors/mq_hr_2019_05.csv.gz', sep=';')
    raw = raw[raw.mq_name.isin(UNSPLIT)].rename(columns={'mq_name': 'site', 'stunde': 'hour', 'q_kfz_mq_hr': 'flow', 'v_kfz_mq_hr': 'speed', 'q_lkw_mq_hr': 'trucks'})
    raw['date'] = pd.to_datetime(raw.tag, format='%d.%m.%Y').dt.strftime('%Y-%m-%d')
    raw = raw[raw.date.isin(DAYS)][['site', 'date', 'hour', 'flow', 'speed', 'trucks']]
    raw.loc[raw.flow < 0, 'flow'] = np.nan
    raw.loc[(raw.speed <= 0) | (raw.flow <= 0), 'speed'] = np.nan
    return raw


def detectors(d):
    """Per-detector hours for the station-days in d."""
    sl = pd.read_csv(B19 / 'step0/site_lanes.csv')
    sl = sl[sl.site.isin(set(d.site))]
    idmap = dict(zip(sl.det_id.astype(str), sl.site))
    out = []
    for ch in pd.read_csv(DATA / 'datasets/berlin-2019-detectors/det_val_hr_2019_05.csv.gz', sep=';', chunksize=500000, dtype={'detid_15': str}):
        ch = ch[ch.detid_15.isin(idmap)]
        ch = ch.assign(site=ch.detid_15.map(idmap), date=pd.to_datetime(ch.tag, format='%d.%m.%Y').dt.strftime('%Y-%m-%d'))
        ch = ch[ch.date.isin(DAYS)]
        out.append(ch[['site', 'detid_15', 'date', 'stunde', 'q_kfz_det_hr', 'v_kfz_det_hr']].rename(columns={'stunde': 'hour', 'q_kfz_det_hr': 'q', 'v_kfz_det_hr': 'v', 'detid_15': 'det'}))
    x = pd.concat(out)
    x.loc[x.q < 0, 'q'] = np.nan
    return x.merge(d[['site', 'date']].drop_duplicates(), on=['site', 'date'])


def net():
    return pickle.loads((B19 / 'step0/net_berlin.pkl').read_bytes())


def site_free(d):
    """metrics.py free_speed: the site's 90th percentile hour."""
    return d.dropna(subset=['speed']).groupby('site').speed.quantile(.9)


def probes():
    z = np.load(B19 / 'probes/edge_15min.npz')
    return {k: z[k] for k in z.files}
