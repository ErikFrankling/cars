#!/usr/bin/env python3
"""Same-gap proposals from both sides must be safe and reproducible."""
import tempfile
from pathlib import Path
from golden import CARS, multilane_net, routes, run, read_cars


def main():
    d = Path(tempfile.mkdtemp(prefix="lc-conflicts-"))
    multilane_net(d, '<node id="a" x="0" y="0"/><node id="b" x="600" y="0"/><node id="c" x="1200" y="0"/>',
                   '<edge id="ab" from="a" to="b" numLanes="3" speed="20"/><edge id="bc" from="b" to="c" numLanes="1" speed="20"/>',
                   '<connection from="ab" to="bc" fromLane="1" toLane="0"/>')
    body = '<route id="r" edges="ab bc"/>'
    for k in range(3):
        for lane in (0, 2):
            body += f'<vehicle id="v{k}_{lane}" type="idm" route="r" depart="0" departLane="{lane}" departPos="{100+60*k}" departSpeed="max"/>'
    routes(d, body)
    tracks = []
    for repeat in range(2):
        path = d / f"cars{repeat}.csv"
        result = run([CARS, "--net", d / "net.xml", "--routes", d / "r.rou.xml", "--dt", "1", "--end", "150", "--seed", "1", "--fcd", path, "--check-overlaps"])
        assert "trips done 6" in result.stdout, result.stdout
        assert "teleports 0" in result.stderr, result.stderr
        tracks.append(read_cars(path))
    assert tracks[0] == tracks[1], "same-gap arbitration changed between identical runs"
    assert any(lane == "ab_1" for track in tracks[0].values() for lane, _, _ in track.values())
    print(f"PASS: both-side same-gap proposals, all 6 arrived, no overlap, identical replay; {d}")


if __name__ == "__main__":
    main()
