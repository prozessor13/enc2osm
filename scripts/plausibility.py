#!/usr/bin/env python3
"""Plausibility of the output against existing OSM seamarks (metric, not pass/fail).

Each output seamark node is matched to the nearest OSM seamark node within 100 m (any type,
each OSM node used at most once, closest pairs first). Reported agreement rates:
  type       seamark:type equal (over all matched pairs)
  colour     seamark:<type>:colour equal (pairs with equal type, both tagged)
  shape      seamark:<type>:shape equal (same)
  character  light character equal (light:character or light:1:character; both tagged)
Usage: plausibility.py OUT.osm.pbf OSM.json REPORT_DIR
OSM.json: Overpass JSON with `node["seamark:type"]` in the region.
"""
import csv
import json
import math
import sys
from collections import Counter, defaultdict

import osmium

R = 100.0


def dist(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * k * 111320, (a[1] - b[1]) * 111320)


def char(t):
    return t.get("seamark:light:character") or t.get("seamark:light:1:character")


def attr(t, a):
    return t.get(f"seamark:{t.get('seamark:type')}:{a}")


def main():
    pbf, osmjson, rep = sys.argv[1:4]
    ours = [((n.location.lon, n.location.lat), dict(n.tags))
            for n in osmium.FileProcessor(pbf, osmium.osm.NODE) if "seamark:type" in n.tags]
    osm = [((e["lon"], e["lat"]), e["tags"], e["id"])
           for e in json.load(open(osmjson))["elements"] if e["type"] == "node"]
    grid = defaultdict(list)
    for i, (p, _, _) in enumerate(osm):
        grid[(int(p[0] * 500), int(p[1] * 1000))].append(i)
    cands = []
    for i, (p, _) in enumerate(ours):
        kx, ky = int(p[0] * 500), int(p[1] * 1000)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((kx + dx, ky + dy), ()):
                    d = dist(p, osm[j][0])
                    if d <= R:
                        cands.append((d, i, j))
    cands.sort()
    used_i, used_j, pairs = set(), set(), []
    for d, i, j in cands:
        if i not in used_i and j not in used_j:
            used_i.add(i)
            used_j.add(j)
            pairs.append((d, i, j))

    stats = {k: Counter() for k in ("type", "colour", "shape", "character")}
    disagree = defaultdict(Counter)
    rows = []
    for d, i, j in pairs:
        a, b = ours[i][1], osm[j][1]
        ta, tb = a["seamark:type"], b.get("seamark:type")
        same = ta == tb
        stats["type"][same] += 1
        if not same:
            disagree["type"][(ta, tb)] += 1
        checks = {"colour": (attr(a, "colour"), attr(b, "colour") if same else None),
                  "shape": (attr(a, "shape"), attr(b, "shape") if same else None),
                  "character": (char(a), char(b))}
        for k, (va, vb) in checks.items():
            if va and vb and (same or k == "character"):
                stats[k][va == vb] += 1
                if va != vb:
                    disagree[k][(ta, va, vb)] += 1
        rows.append([f"{d:.0f}", ta, tb, a.get("seamark:name", ""), b.get("seamark:name", ""),
                     checks["colour"][0] or "", checks["colour"][1] or "",
                     checks["shape"][0] or "", checks["shape"][1] or "",
                     checks["character"][0] or "", checks["character"][1] or "",
                     a.get("enc:cell"), osm[j][2]])
    with open(f"{rep}/plausibility_pairs.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dist_m", "type_enc", "type_osm", "name_enc", "name_osm", "colour_enc",
                    "colour_osm", "shape_enc", "shape_osm", "char_enc", "char_osm", "enc_cell",
                    "osm_node"])
        w.writerows(rows)
    out = {"output_nodes": len(ours), "osm_nodes": len(osm), "matched_pairs": len(pairs),
           "rates": {k: {"agree": c[True], "disagree": c[False],
                         "rate": round(c[True] / (c[True] + c[False]), 4) if c else None}
                     for k, c in stats.items()},
           "top_disagreements": {k: [[list(key), n] for key, n in c.most_common(15)]
                                 for k, c in disagree.items()}}
    with open(f"{rep}/plausibility.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "top_disagreements"}, indent=1))
    for k, c in disagree.items():
        print(f"-- {k}")
        for key, n in c.most_common(12):
            print(f"   {n:4d}  {key}")


if __name__ == "__main__":
    main()
