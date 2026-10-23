"""Phase 7: write nodes, ways and relations with pyosmium (format from the file extension)."""

from __future__ import annotations

import os

import osmium
from osgeo import ogr
from osmium.osm import mutable

from enc2osm import __version__
from enc2osm.pass2 import PointObj
from enc2osm.rejoin import Merged

MAX_WAY_NODES = 2000
QUANT = 10_000_000  # 1e-7 degree


class VertexStore:
    """Way vertices deduplicated by coordinates quantized to 1e-7 degree."""

    def __init__(self, first_id: int):
        self.next_id = first_id  # internal ids are positive and ascending; signed on output
        self.ids: dict[tuple[int, int], int] = {}
        self.order: list[tuple[int, tuple[int, int]]] = []

    def get(self, x: float, y: float) -> int:
        k = (round(x * QUANT), round(y * QUANT))
        nid = self.ids.get(k)
        if nid is None:
            nid = self.next_id
            self.next_id += 1
            self.ids[k] = nid
            self.order.append((nid, k))
        return nid


def _ring_ids(ring: ogr.Geometry, vs: VertexStore) -> list[int]:
    ids = [vs.get(*ring.GetPoint_2D(i)) for i in range(ring.GetPointCount())]
    return [n for k, n in enumerate(ids) if k == 0 or n != ids[k - 1]]


def _chunks(ids: list[int]) -> list[list[int]]:
    """Split a node list into ways of at most MAX_WAY_NODES sharing their end nodes."""
    out, start = [], 0
    while start < len(ids) - 1:
        end = min(start + MAX_WAY_NODES - 1, len(ids) - 1)
        out.append(ids[start:end + 1])
        start = end
    return out


class Plan:
    def __init__(self, points: list[PointObj], shapes: list[Merged]):
        self.points = points
        self.vs = VertexStore(len(points) + 1)
        self.ways: list[tuple[list[int], dict]] = []
        self.rels: list[tuple[list[tuple[str, int, str]], dict]] = []
        for s in shapes:
            g = ogr.CreateGeometryFromWkb(s.wkb)
            if s.kind == "line":
                self._line(g, s.tags)
            else:
                self._area(g, s.tags)

    def _way(self, ids, tags) -> int:
        self.ways.append((ids, tags))
        return len(self.ways)

    def _line(self, g: ogr.Geometry, tags: dict) -> None:
        for i in range(g.GetGeometryCount()):
            ids = _ring_ids(g.GetGeometryRef(i), self.vs)
            if len(ids) < 2:
                continue
            t = dict(tags)
            if ids[0] == ids[-1]:
                t["area"] = "no"  # closed but linear: keep renderers from making it a polygon
            for part in _chunks(ids):
                self._way(part, t)

    def _area(self, g: ogr.Geometry, tags: dict) -> None:
        polys = [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())]
        rings = [[_ring_ids(p.GetGeometryRef(r), self.vs) for r in range(p.GetGeometryCount())]
                 for p in polys]
        rings = [[r for r in pr if len(r) >= 4] for pr in rings]
        rings = [pr for pr in rings if pr]
        if not rings:
            return
        if len(rings) == 1 and len(rings[0]) == 1 and len(rings[0][0]) <= MAX_WAY_NODES:
            self._way(rings[0][0], dict(tags))
            return
        members = []
        for pr in rings:
            for r, ids in enumerate(pr):
                role = "outer" if r == 0 else "inner"
                for part in _chunks(ids):
                    members.append(("w", self._way(part, {}), role))
        t = dict(tags)
        t["type"] = "multipolygon"
        self.rels.append((members, t))


def write(path: str, points: list[PointObj], shapes: list[Merged], attribution: str,
          bbox: tuple[float, float, float, float] | None, negative_ids: bool = False) -> dict:
    """IDs are 1, 2, 3, ... per object type (Planetiler requires ascending, non-negative node
    IDs); with negative_ids they are -1, -2, -3, ... (see docs/DECISIONS.md D16)."""
    sign = -1 if negative_ids else 1
    plan = Plan(points, shapes)
    if os.path.exists(path):
        os.remove(path)
    hdr = osmium.io.Header()
    hdr.set("generator", f"enc2osm {__version__}")
    hdr.set("source", attribution)
    if bbox:
        hdr.add_box(osmium.osm.Box(osmium.osm.Location(bbox[0], bbox[1]),
                                   osmium.osm.Location(bbox[2], bbox[3])))
    w = osmium.SimpleWriter(path, header=hdr)
    try:
        for i, p in enumerate(points, 1):
            w.add_node(mutable.Node(id=sign * i, location=(p.x, p.y), tags=p.tags))
        for nid, (qx, qy) in plan.vs.order:
            w.add_node(mutable.Node(id=sign * nid, location=(qx / QUANT, qy / QUANT), tags={}))
        for i, (ids, tags) in enumerate(plan.ways, 1):
            w.add_way(mutable.Way(id=sign * i, nodes=[sign * n for n in ids], tags=tags))
        for i, (members, tags) in enumerate(plan.rels, 1):
            w.add_relation(mutable.Relation(
                id=sign * i, members=[(t, sign * r, role) for t, r, role in members], tags=tags))
    finally:
        w.close()
    return {"seamark_nodes": len(points), "vertex_nodes": len(plan.vs.order),
            "ways": len(plan.ways), "relations": len(plan.rels)}
