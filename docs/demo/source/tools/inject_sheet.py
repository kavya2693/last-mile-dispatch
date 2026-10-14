"""Inline an exported JSON file into a composition (renders cannot fetch files).

Replaces the block  /* NAME:BEGIN */ const NAME = {...}; /* NAME:END */  in the HTML file.

Usage: python3 tools/inject_sheet.py assets/rider_board.json compositions/value.html --name SHEET
       python3 tools/inject_sheet.py assets/run_series.json compositions/s04-routes.html --name SERIES
"""

import argparse
import json
import re

ap = argparse.ArgumentParser()
ap.add_argument("data")
ap.add_argument("html")
ap.add_argument("--name", default="SHEET")
a = ap.parse_args()

with open(a.data) as fh:
    d = json.load(fh)
with open(a.html) as fh:
    html = fh.read()
n = a.name
block = f"/* {n}:BEGIN */ const {n} = " + json.dumps(d, separators=(",", ":")) + f"; /* {n}:END */"
html, k = re.subn(rf"/\* {n}:BEGIN \*/.*?/\* {n}:END \*/", lambda _: block, html, flags=re.S)
assert k == 1, f"{n} marker not found in {a.html}"
with open(a.html, "w") as fh:
    fh.write(html)
print("injected", a.data, "->", a.html, f"({len(block):,} chars)")
