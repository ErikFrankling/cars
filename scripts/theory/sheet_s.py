"""Signal forecasts of B §2 at real saturation: 1,750, sweep 1,640-1,900 (R §2), in place of 1,800. Prints one row per forecast line."""
import math as m


def sig(q, S, C=90, g=40, kj=1 / 7.5, w=19.3 / 3.6, uf=50 / 3.6, Tp=.25):
    q1, S1 = q / 3600, S / 3600
    x, r, ka = q1 * C / (S1 * g), C - g, q1 / uf
    u = q1 / (kj - ka)
    ts = r * w / (w - u)
    gs = r * q1 / (S1 - q1)
    d1 = C * (1 - g / C) ** 2 / (2 * (1 - q1 / S1)) if x < 1 else r / 2
    web = d1 + x ** 2 / (2 * q1 * (1 - x)) - .65 * (C / q1 ** 2) ** (1 / 3) * x ** (2 + 5 * g / C) if x < 1 else float('inf')
    cap = S * g / C
    CT, x0 = cap * Tp, .67 + S1 * g / 600
    Q0 = CT / 4 * ((x - 1) + m.sqrt((x - 1) ** 2 + 12 * max(x - x0, 0) / CT)) if x > x0 else 0
    return dict(x=x, cap=cap, N=u * ts * kj, L=u * ts, gs=gs, d1=d1, web=web, akc=d1 + Q0 / cap * 3600)


for S in (1640, 1750, 1900):
    print(f'== S {S}')
    print(' S4 c', round(S * 40 / 90))
    a = sig(600, S)
    print(' S5 qa 600: N %.1f L %.0f gs %.1f; S6 d1 %.1f' % (a['N'], a['L'], a['gs'], a['d1']))
    print(' S7 Webster', [(q, round(sig(q, S)['x'], 2), round(sig(q, S)['web'], 1)) for q in (304, 448, 600, 720)])
    print(' S8 Akcelik', [(q, round(sig(q, S)['x'], 2), round(sig(q, S)['akc'], 1)) for q in (720, 900)], 'growth qa 900 15 min', round((900 - S * 40 / 90) / 4, 1))
    print(' N1 S*21/60', round(S * 21 / 60), ' N2 S*40.5/90', round(S * 40.5 / 90), ' N3 c S*36/90', round(S * 36 / 90), ' N3b c', round(S * 40.5 / 90))
    print(' N9 per cycle offset0 S*40/3600 %.1f, Hamburg 26 s %.1f' % (S * 40 / 3600, S * 26 / 3600))


def n1_plateau():
    """N1 plateau by the scene's own rule, q at least 0.95 of the top, on the plain cuts and with granularity (DG 2008 eq. 7-8)."""
    import contextlib
    import io
    import sys
    sys.argv = ['cuts']
    with contextlib.redirect_stdout(io.StringIO()):
        import cuts
    for S in (1750, 1800):
        mm = cuts.mfd(l=123, C=60, G=21, delta=0, uf=13.4, w=5.4, kj=0.13, s=S / 3600, rand=True)
        ks = [i * 0.13 / 400 for i in range(1, 400)]
        for lab, q in (('plain', [mm['Q'](k) for k in ks]), ('granular N 16', [cuts.granular(mm, 0.13, 16, k) for k in ks])):
            top = max(q)
            on = [k for k, x in zip(ks, q) if x >= 0.95 * top]
            print(f' N1 S {S} {lab}: top {top * 3600:.0f}, 0.95 plateau {on[0] * 1000:.0f}-{on[-1] * 1000:.0f} veh/km')


n1_plateau()
