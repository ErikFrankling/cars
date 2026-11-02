#!/usr/bin/env python3
"""Open a Xuancheng demo .db read-only if it is SQLite and print schema and rows. Arg: path."""
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    for name, sql in c.execute("select name, sql from sqlite_master"):
        print(name, sql)
        print(" rows", c.execute(f'select count(*) from "{name}"').fetchone())
        for r in c.execute(f'select * from "{name}" limit 4'): print("  ", str(r)[:400])
except Exception as e:
    print("error", e)
