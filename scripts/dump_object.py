#!/usr/bin/env python3
"""Dev helper: print the raw S-57 attributes of an object and its slaves (golden-test input).

Usage: dump_object.py CELL.000 [LNAM ...]   (no LNAM: list candidates per class)
"""
import sys
from collections import Counter

from enc2osm import aggregate, extract, mapping
from enc2osm.inventory import read_cell

m = mapping.load()
cell = read_cell(__import__("pathlib").Path(sys.argv[1]))
st = Counter()
fs = extract.read_features(cell.path, m, m.classes("v1"), cell.duni, cell.huni, st)
ags = aggregate.aggregate(fs, m, st)
if len(sys.argv) == 2:
    for a in ags:
        if a.kind == "point":
            print(a.cls, a.lnam, a.primary.attrs.get("OBJNAM"), [s.cls for s in a.slaves])
    sys.exit()
for a in ags:
    if a.lnam in sys.argv[2:]:
        print(f"== {cell.name} {a.cls} {a.lnam} ({a.primary.x:.7f}, {a.primary.y:.7f})")
        for f in ([a.master] if a.master else []) + a.slaves:
            print(f"   {f.cls} {f.lnam}: {f.attrs}")
