#!/usr/bin/env python3
"""What moves when a parameter moves. Every number research/physics-provenance.md calls invented has a line here,
and the driver gap law is swept against Trafikverket's saturation flows.

    python3 scripts/physics_sensitivity.py driver|invented --out DIR [--cars BIN]
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('physics_tests', ROOT / 'scripts/physics_tests.py')
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
gspec = importlib.util.spec_from_file_location('intersection_gallery', ROOT / 'scripts/intersection_gallery.py')
GAL = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(GAL)
TARGET = dict(through=1900, right=1700, left=1700, double=1500)


def tune(pairs):
    return [x for k, v in pairs.items() for x in ('--tune', f'{k}={v}')]


GRID = [(tau, b, bh, 4.17, lo) for tau in (0.4, 0.5, 0.6) for b, bh in ((3.0, 4.5), (2.5, 3.5), (3.0, 4.0)) for lo in (7.0, 8.3)] + [(1.35, 4.5, 4.5, 3.0, 7.0), (0.5, 3.0, 4.5, 3.0, 7.0)]


def driver(a):
    """Gipps' form: gap = tau v + v^2/2 (1/b - 1/b_hat). The grid is what the two TRVMB targets leave open."""
    rows = []
    for tau, b, bh, cap, b_lo in a.grid or GRID:
        if True:
            if True:
                for radius in (None, 10):
                    row = dict(tau=tau, b=b, b_hat=bh, curve_cap=cap, b_lo=b_lo, radius=radius)
                    for kind in ('through', 'right', 'left', 'double'):
                        if kind == 'through' and radius:
                            continue
                        d = Path(a.out) / f'driver-{kind}-{radius}'
                        d.mkdir(parents=True, exist_ok=True)
                        if not (d / 'net.xml').exists():
                            T.capacity_net(d, kind, radius)
                        for dt in (1.0, 0.1):
                            flow, spacing, rep = T.saturation(d, kind, dt, tune(dict(tau=tau, driver_b=b, leader_b=bh, curve_cap=cap, car_b_lo=b_lo)), f't{dt}')
                            row[f'{kind}_{dt}'] = round(flow)
                            row['contacts'] = row.get('contacts', 0) + rep['collision_incidents']
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    Path(a.out, 'driver.json').write_text(json.dumps(rows, indent=1))


INVENTED = dict(
    zone_distance=(2.2, 2.6, 3.0), width_margin=(0.0, 0.1, 0.3), claim_scale=(0.7, 1.0, 1.3), queue_speed=(1.0, 5.0, 8.0), exit_comply=(0.5, 0.9, 1.0),
    lc_path=(0, 1), certificate=(0, 1), arbiter=(0, 1), exit_clear=(0, 1), curve_cap=(3.0, 4.17), car_b_lo=(7.0, 8.3),
    tc_clear=(0.6, 1.2, 1.8), tc_scale=(0.6, 0.8, 1.0), zone_time=(0, 1, 2), zones_ahead=(0, 1), rewind=(0, 1), lc_gap=(0.3, 0.6, 1.0), lat_standing=(0.0, 0.1, 0.3), lost_after=(0, 120, 300),
)


def invented(a):
    """Moves one parameter at a time on junctions under load: flow, travel time, contacts, stuck vehicles."""
    rows = []
    for fixture in ('priority', 'signal', 'roundabout', 'on-ramp'):
        d = Path(a.out) / f'fix-{fixture}'
        d.mkdir(parents=True, exist_ok=True)
        if not (d / 'net.xml').exists():
            GAL.FIXTURES[fixture](d)
        for dt in (1.0, 0.1):
            for name, values in INVENTED.items():
                for v in values:
                    tag = f'{name}-{v}-{dt}'
                    T.run([*T.LOCK, a.cars, 'run', '--net', d / 'net.xml', '--routes', d / 'routes.xml', '--dt', dt, '--end', 700, '--seed', 1, '--report-json', d / f'{tag}.json', '--trip-csv', d / f'{tag}.csv', '--tune', f'{name}={v}'])
                    rep = json.loads((d / f'{tag}.json').read_text())
                    trips = T.pd.read_csv(d / f'{tag}.csv')
                    row = dict(fixture=fixture, dt=dt, name=name, value=v, arrived=rep['arrived'], inserted=rep['inserted'], duration=round(float(trips.duration.mean()), 1) if len(trips) else None, loss=round(float(trips.time_loss.mean()), 1) if len(trips) else None,
                               contacts=rep['collision_incidents'], kinds={k: n for k, n in rep['incidents_by_kind'].items() if n}, ungranted=rep['ungranted'], stuck=rep['gridlock_worst_stuck'], denied=rep['denied'])
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    Path(a.out, 'invented.json').write_text(json.dumps(rows, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('what', choices=['driver', 'invented'])
    p.add_argument('--out', required=True)
    p.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    a = p.parse_args()
    a.grid = None
    T.A = argparse.Namespace(cars=a.cars, out=a.out, tune_args=[], radius=None)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    dict(driver=driver, invented=invented)[a.what](a)


if __name__ == '__main__':
    main()
