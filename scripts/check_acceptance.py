#!/usr/bin/env python3
"""Automated acceptance checks on a built PBF (criteria 3, 4, 5, 9).

Usage: check_acceptance.py OUT.osm.pbf REPORT_DIR INPUT... [--tol 50]

3  coverage invariants: points inside the buffered effective area of their enc:cell; ways and
   multipolygons inside the union of the effective areas of their enc:cell list; union of
   effective areas == union of M_COVR coverages; effective areas do not overlap.
4  dedup invariant: no two seamark nodes *from different cells* with the same type and the same
   non-empty name within 2x tolerance, except pairs logged as ambiguous; ambiguous < 1 % of seam
   candidates. Same-name pairs within one cell are distinct S-57 objects of that cell (not seam
   duplicates); they are listed for transparency (see docs/DECISIONS.md D17).
5  no orphaned slaves: every LIGHTS/TOPMAR/FOGSIG read is on a structure or standalone.
9  every seamark:type and every enumeration value in the output exists in the mapping tables.
Exit status 1 if any check fails. Writes REPORT_DIR/acceptance.json.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict

import osmium
from osgeo import ogr

from enc2osm import coverage, inventory, mapping
from enc2osm.dedup import Grid
from enc2osm.pass2 import PointObj

EPS = 1e-7  # degrees, numeric slack for "inside"
HIDE = ("examples", "pass", "same_cell_list")


def load(pbf):
    nodes, lines = [], []
    fp = osmium.FileProcessor(pbf).with_locations().with_areas()
    wkb = osmium.geom.WKBFactory()
    for o in fp:
        if o.is_node() and "seamark:type" in o.tags:
            nodes.append((o.id, o.location.lon, o.location.lat, dict(o.tags)))
        elif o.is_way() and "seamark:type" in o.tags and not o.is_closed():
            lines.append((f"w{o.id}", ogr.CreateGeometryFromWkb(bytes.fromhex(
                wkb.create_linestring(o))), dict(o.tags)))
        elif o.is_way() and "seamark:type" in o.tags and o.tags.get("area") == "no":
            lines.append((f"w{o.id}", ogr.CreateGeometryFromWkb(bytes.fromhex(
                wkb.create_linestring(o))), dict(o.tags)))
        elif o.is_area() and "seamark:type" in o.tags:
            lines.append((f"a{o.id}", ogr.CreateGeometryFromWkb(bytes.fromhex(
                wkb.create_multipolygon(o))), dict(o.tags)))
    return nodes, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument("report")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--tol", type=float, default=50.0)
    a = ap.parse_args()
    res, ok = {}, True

    cells, _ = inventory.build(a.inputs)
    effs = coverage.resolve(cells)
    by = {c.name: c for c in cells}
    nodes, shapes = load(a.pbf)

    # --- 3 coverage invariants
    bad_pts = []
    buffered = {}
    for nid, x, y, t in nodes:
        c = by[t["enc:cell"]]
        if c.name not in buffered:
            tol = coverage.m_to_deg(a.tol, max(abs(c.bbox[1]), abs(c.bbox[3])))
            g = effs[c.name].geom
            buffered[c.name] = g.Buffer(tol + EPS) if not g.IsEmpty() else g
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AddPoint_2D(x, y)
        if buffered[c.name].IsEmpty() or not buffered[c.name].Intersects(pt):
            bad_pts.append(nid)
    bad_shapes = []
    for sid, g, t in shapes:
        u = ogr.Geometry(ogr.wkbMultiPolygon)
        for name in t["enc:cell"].split(";"):
            e = effs[name].geom
            for i in range(e.GetGeometryCount()):
                u.AddGeometry(e.GetGeometryRef(i))
        u = u.UnionCascaded().Buffer(EPS)
        if not g.Within(u):
            outside = g.Difference(u)
            if not outside.IsEmpty() and (outside.GetArea() > 1e-12 or outside.Length() > 1e-6):
                bad_shapes.append(sid)
    covs, eff_u = ogr.Geometry(ogr.wkbMultiPolygon), ogr.Geometry(ogr.wkbMultiPolygon)
    total = 0.0
    for c in cells:
        for g, acc in ((c.coverage, covs), (effs[c.name].geom, eff_u)):
            for i in range(g.GetGeometryCount()):
                acc.AddGeometry(g.GetGeometryRef(i))
        total += effs[c.name].geom.GetArea()
    u_cov, u_eff = covs.UnionCascaded(), eff_u.UnionCascaded()
    symdiff = u_cov.SymDifference(u_eff).GetArea()
    overlap = total - u_eff.GetArea()
    slivers = sum(e.slivers_dropped for e in effs.values())
    c3 = {"points_checked": len(nodes), "points_outside": len(bad_pts),
          "shapes_checked": len(shapes), "shapes_outside": len(bad_shapes),
          "union_symdiff_deg2": symdiff, "overlap_deg2": overlap, "slivers_dropped": slivers,
          "examples": {"points": bad_pts[:10], "shapes": bad_shapes[:10]}}
    c3["pass"] = not bad_pts and not bad_shapes and symdiff < 1e-9 and abs(overlap) < 1e-9
    res["3_coverage"] = c3

    # --- 4 dedup invariant
    amb = set()
    seam = json.load(open(f"{a.report}/stats.json"))
    with open(f"{a.report}/dedup.csv") as f:
        for r in csv.DictReader(f):
            if r["action"] == "ambiguous":
                amb.add(frozenset({(r["kept_cell"], r["kept_lnam"]),
                                   (r["other_cell"], r["other_lnam"])}))
    pts = [PointObj(t["enc:cell"], 0, "", t.get("enc:lnam", ""), x, y, t)
           for _, x, y, t in nodes]
    grid = Grid(pts, a.tol)
    pairs, same_cell = [], []
    for i, p in enumerate(pts):
        name = p.tags.get("seamark:name")
        if not name:
            continue
        for j in grid.near(p, 2 * a.tol):
            q = pts[j]
            if j > i and q.tags.get("seamark:name") == name and \
                    q.tags["seamark:type"] == p.tags["seamark:type"]:
                key = frozenset({(p.cell, p.lnam), (q.cell, q.lnam)})
                if key not in amb:
                    d = math.hypot((p.x - q.x) * math.cos(math.radians(p.y)) * 111320,
                                   (p.y - q.y) * 111320)
                    row = [p.tags["seamark:type"], name, p.cell, p.lnam, q.cell, q.lnam,
                           round(d, 1)]
                    (same_cell if p.cell == q.cell else pairs).append(row)
    cand = seam.get("seam_candidates", 0)
    share = len(amb) / cand if cand else 0.0
    res["4_dedup"] = {"violations": len(pairs), "examples": pairs[:20],
                      "same_cell_same_name_pairs": len(same_cell), "same_cell_list": same_cell,
                      "ambiguous": len(amb), "seam_candidates": cand,
                      "ambiguous_share": round(share, 4),
                      "pass": not pairs and share < 0.01}

    # --- 5 orphaned slaves
    gs = seam["global_stats"]
    c5 = {}
    for cls in ("LIGHTS", "TOPMAR", "FOGSIG", "DAYMAR", "RTPBCN"):
        read = gs.get(f"read:{cls}", 0)
        skipped = sum(v for k, v in gs.items() if k.startswith(f"skipped_geometry:{cls}:"))
        on = gs.get(f"slave_on_structure:{cls}", 0)
        alone = gs.get(f"slave_standalone:{cls}", 0)
        c5[cls] = {"read": read, "on_structure": on, "standalone": alone,
                   "skipped_geometry": skipped, "orphaned": read - on - alone - skipped}
    res["5_slaves"] = {**c5, "pass": all(v["orphaned"] == 0 for v in c5.values())}

    # --- 9 no free-text leakage
    m = mapping.load()
    types = m.all_types()
    enum_vals = defaultdict(set)
    for acr, at in m.attributes.items():
        if at.get("kind") in ("enum", "list"):
            enum_vals[at["key"]] |= set(m.values[at.get("values", acr)].values())
    bad_types, bad_vals = set(), set()
    for _, _, _, t in nodes:
        if t["seamark:type"] not in types:
            bad_types.add(t["seamark:type"])
    for _, _, t in shapes:
        if t["seamark:type"] not in types:
            bad_types.add(t["seamark:type"])
    for t in [n[3] for n in nodes] + [s[2] for s in shapes]:
        for k, v in t.items():
            if not k.startswith("seamark:") or k in ("seamark:type", "seamark:name"):
                continue
            key = k.rsplit(":", 1)[1]
            if key in enum_vals:
                for part in v.split(";"):
                    if part not in enum_vals[key]:
                        bad_vals.add((k, part))
    res["9_vocabulary"] = {"unknown_types": sorted(bad_types),
                           "unknown_values": sorted(map(list, bad_vals))[:50],
                           "pass": not bad_types and not bad_vals}

    for k, v in res.items():
        ok &= v["pass"]
        print(f"{k:14} {'PASS' if v['pass'] else 'FAIL'}  "
              f"{ {kk: vv for kk, vv in v.items() if kk not in HIDE} }")
    with open(f"{a.report}/acceptance.json", "w") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=list)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
