#!/usr/bin/env python3
"""Dev helper: attribute/value frequencies per object class over a set of cells."""
import collections
import sys

from enc2osm import s57

SKIP = {"RCID", "PRIM", "GRUP", "OBJL", "RVER", "AGEN", "FIDN", "FIDS", "LNAM", "LNAM_REFS",
        "FFPT_RIND", "OBJNAM", "NOBJNM", "INFORM", "NINFOM", "SORDAT", "SORIND", "RECDAT",
        "RECIND", "SCAMIN", "SCAMAX", "TXTDSC", "NTXTDS", "PICREP"}
classes = sys.argv[1].split(",")
stats = collections.defaultdict(collections.Counter)
geoms = collections.Counter()
for path in s57.discover(sys.argv[2:]):
    ds = s57.open_cell(path)
    for cls in classes:
        lyr = ds.GetLayerByName(cls)
        if lyr is None:
            continue
        for f in lyr:
            g = f.GetGeometryRef()
            geoms[(cls, g.GetGeometryName() if g else None)] += 1
            for k, v in f.items().items():
                if k in SKIP or v in (None, "", []):
                    continue
                if isinstance(v, list):
                    v = ",".join(v)
                if isinstance(v, float):
                    v = "<num>"
                stats[(cls, k)][str(v)] += 1
for k, n in sorted(geoms.items(), key=str):
    print("GEOM", k, n)
for (cls, k), c in sorted(stats.items()):
    print(f"{cls}.{k}: " + "  ".join(f"{v}×{n}" for v, n in c.most_common(25)))
