#!/usr/bin/env python3
"""Generated roads for cars-gui, written to the directory given last, as net.xml and routes.xml.

Usage: gui_scenarios.py <phenomena or gallery name> <dir>
       gui_scenarios.py d8 <net> <veh/h> <dir>
Run inside nix develop: needs netconvert. The roads come from phenomena.py and intersection_gallery.py.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import intersection_gallery
import phenomena

# demand.py writes the CarsAV type; human-only is the default, so routes start with a plain human driver.
HUMAN = '<vType id="av" vClass="passenger" length="5" minGap="2.5" accel="2.6" decel="4.5" sigma="0.5" tau="1"/>'


def d8(net, rate, d):
    out = d / 'routes.xml'
    subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', net, '--out', str(out), '--demand', rate,
                    '--mix', 'M', '--end', '800', '--seed', '0'], check=True)
    out.write_text(re.sub(r'<vType id="av".*?</vType>', HUMAN, out.read_text(), count=1))


def main():
    args = sys.argv[1:]
    d = Path(args[-1])
    d.mkdir(parents=True, exist_ok=True)
    if args[0] == 'd8':
        d8(args[1], args[2], d)
    elif args[0] in phenomena.SCENARIOS:
        phenomena.SCENARIOS[args[0]](d)
    elif args[0] in intersection_gallery.FIXTURES:
        intersection_gallery.FIXTURES[args[0]](d)
    else:
        sys.exit(f'unknown generated road {args[0]}')


if __name__ == '__main__':
    main()
