#!/usr/bin/env python3
"""Classify report/dropped_without_counterpart.csv against the output PBF (criterion 8).

For every dropped object: nearest written object of the same seamark:type and of any type,
and the issue dates of the dropping and the covering cell. Heuristic class:
  position   - same type exists in the output within 500 m (offset beyond 2x tolerance)
  type       - a different seamark:type sits within 2x tolerance (e.g. landmark vs light_major)
  edition    - nothing near; covering cell is older than the dropped cell's (newer object lost)
  not_charted- nothing near; covering cell is newer or same age (larger scale omits it)
Usage: classify_dropped.py OUT.osm.pbf REPORT_DIR [TOL_M]
"""
import csv
import math
import sys
from collections import Counter

import osmium

pbf, rep = sys.argv[1], sys.argv[2]
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
nodes = [(n.location.lon, n.location.lat, n.tags.get("seamark:type"), n.tags.get("seamark:name"))
         for n in osmium.FileProcessor(pbf, osmium.osm.NODE) if "seamark:type" in n.tags]


def dist(x1, y1, x2, y2):
    k = math.cos(math.radians((y1 + y2) / 2))
    return math.hypot((x1 - x2) * k * 111320, (y1 - y2) * 111320)


rows = list(csv.DictReader(open(f"{rep}/dropped_without_counterpart.csv")))
out, cnt = [], Counter()
for r in rows:
    x, y, typ = float(r["lon"]), float(r["lat"]), r["seamark_type"]
    near = [(dist(x, y, nx, ny), t, nm) for nx, ny, t, nm in nodes
            if abs(nx - x) < 0.02 and abs(ny - y) < 0.02]
    same = min((d for d, t, _ in near if t == typ), default=None)
    anyt = min(((d, t) for d, t, _ in near), default=(None, None))
    if same is not None and same <= 500:
        cls = "position"
    elif anyt[0] is not None and anyt[0] <= 2 * tol:
        cls = "type"
    elif r["covering_issue_date"] and r["covering_issue_date"] < r["issue_date"]:
        cls = "edition"
    else:
        cls = "not_charted"
    cnt[cls] += 1
    out.append({**r, "nearest_same_type_m": "" if same is None else f"{same:.0f}",
                "nearest_any_m": "" if anyt[0] is None else f"{anyt[0]:.0f}",
                "nearest_any_type": anyt[1] or "", "class": cls})
with open(f"{rep}/dropped_classified.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]) if out else ["class"])
    w.writeheader()
    w.writerows(out)
print(dict(cnt))
