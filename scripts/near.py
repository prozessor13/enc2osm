#!/usr/bin/env python3
"""Dev helper: list all S-57 objects of a cell (any layer) within R metres of lon,lat.

Usage: near.py CELL.000 LON LAT [R_M]
"""
import math
import sys

from enc2osm import s57

path, lon, lat = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
r = float(sys.argv[4]) if len(sys.argv) > 4 else 300.0
dlat = r / 111320
dlon = dlat / math.cos(math.radians(lat))
ds = s57.open_cell(path)
for i in range(ds.GetLayerCount()):
    lyr = ds.GetLayer(i)
    name = lyr.GetName()
    if name in ("DSID", "IsolatedNode", "ConnectedNode", "Edge", "Face") or name.startswith("M_") \
            or lyr.GetLayerDefn().GetGeomFieldCount() == 0:
        continue
    lyr.SetSpatialFilterRect(lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    for f in lyr:
        g = f.GetGeometryRef()
        if g is None:
            continue
        if g.GetGeometryName() == "POINT":
            d = math.hypot((g.GetX() - lon) * 111320 * math.cos(math.radians(lat)),
                           (g.GetY() - lat) * 111320)
            where = f"{d:6.0f} m"
        else:
            where = g.GetGeometryName()[:8]
        keep = {k: v for k, v in f.items().items() if v not in (None, "", []) and k in
                ("OBJNAM", "CATOBS", "CATWRK", "WATLEV", "VALSOU", "CATPLE", "CATMOR", "CATLMK",
                 "CATSLC", "CONDTN", "SORDAT")}
        if g.GetGeometryName() != "POINT" and name in ("DEPARE", "LNDARE", "SEAARE", "DEPCNT",
                                                       "COALNE", "SOUNDG", "BUAARE", "LNDRGN"):
            continue
        print(f"{name:7} {where} {keep}")
