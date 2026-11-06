"""Held-out recordings (research/truth/measure/HOLDOUT.md). Every loader filters through here."""
HOLD = {
    'highD': {58, 59, 60},
    'inD': {30, 31, 32},
    'rounD': {20, 21, 22, 23},
    'exiD': {73, 74, 75, 76, 77},
    'sind': {'Xi_an'},
    'dlrht_hours_utc': (14, 16),
    'tgsim': {'I90mov'},
}


def held(ds, rec):
    return rec in HOLD.get(ds, ())
