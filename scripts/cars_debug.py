#!/usr/bin/env python3
"""The debugging tools behind `cars why`, `cars tsd`, `cars jam`, `cars compare`, `cars junction` and `cars dist`.
Every tool prints what an agent needs on the terminal and writes a PNG it can view. crates/cars-cli/DEBUGGING.md."""
import importlib
import sys
from pathlib import Path

TOOLS = ['why', 'tsd', 'jam', 'compare', 'junction', 'dist']


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        raise SystemExit(f'usage: cars_debug.py {"|".join(TOOLS)} ... (each has --help)')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    tool = sys.argv[1]
    importlib.import_module(f'dbg.{tool}').main(sys.argv[2:])


if __name__ == '__main__':
    main()
