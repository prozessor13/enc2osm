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
MAX_VALUE = 255  # OSM limit for tag values (characters)


def fit_tags(tags: dict, stats: dict) -> dict:
    """Keep every tag value within the OSM limit of 255 characters.

    `;`-lists of provenance (enc:cell, enc:lnam, ...) of features re-joined from many cells keep
    as many entries as fit plus ';…' and get `<key>_count`; free text is cut with '…'.
    Every shortened value is counted in the stats (key `tag_shortened:<key>`).
    """
    if all(len(v) <= MAX_VALUE for v in tags.values()):
        return tags
    out = dict(tags)
    for k, v in tags.items():
        if len(v) <= MAX_VALUE:
            continue
        stats[f"tag_shortened:{k}"] = stats.get(f"tag_shortened:{k}", 0) + 1
        if k.startswith("enc:") and ";" in v:
            items = v.split(";")
            kept = []
            for it in items:
                if len(";".join(kept + [it])) + 2 > MAX_VALUE:
                    break
                kept.append(it)
            out[k] = ";".join(kept) + ";…"
            out[f"{k}_count"] = str(len(items))
        else:
            out[k] = v[:MAX_VALUE - 1] + "…"
    return out
QUANT = 10_000_000  # 1e-7 degree


class VertexStore:
    """Way vertices deduplicated by coordinates quantized to 1e-7 degree.

    In memory up to `spill_at` vertices, then moved to the sqlite temp store behind the same
    interface (CLAUDE.md: on-disk store if memory becomes an issue). Ids are positive and
    ascending in first-seen order; the writer applies the sign.
    """

    def __init__(self, first_id: int, store=None, spill_at: int = 3_000_000):
        self.next_id = first_id
        self.ids: dict[tuple[int, int], int] = {}
        self.order: list[tuple[int, tuple[int, int]]] = []
        self.store, self.spill_at, self.spilled = store, spill_at, False

    def get(self, x: float, y: float) -> int:
        k = (round(x * QUANT), round(y * QUANT))
        if self.spilled:
            nid = self.store.vertex_get(k)
        else:
            nid = self.ids.get(k)
        if nid is None:
            nid = self.next_id
            self.next_id += 1
            if self.spilled:
                self.store.vertex_put(k, nid)
            else:
                self.ids[k] = nid
                self.order.append((nid, k))
                if self.store is not None and len(self.order) >= self.spill_at:
                    self._spill()
        return nid

    def _spill(self) -> None:
        self.store.vertex_bulk(self.order)
        self.ids.clear()
        self.order = []
        self.spilled = True

    def items(self):
        """(id, (qx, qy)) in id order."""
        if self.spilled:
            yield from self.store.vertices()
        else:
            yield from self.order


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
    """First pass over lines/areas: assign vertex ids, spool ways/relations into the store."""

    def __init__(self, n_points: int, shapes, store, spill_at: int = 3_000_000):
        self.vs = VertexStore(n_points + 1, store, spill_at)
        self.store = store
        self.n_ways = 0
        self.n_rels = 0
        for kind, _cls, wkb, tags in shapes:
            g = ogr.CreateGeometryFromWkb(wkb)
            if kind == "line":
                self._line(g, tags)
            else:
                self._area(g, tags)

    def _way(self, ids, tags) -> int:
        self.n_ways += 1
        self.store.add_way(self.n_ways, ids, tags)
        return self.n_ways

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
        self.n_rels += 1
        self.store.add_rel(self.n_rels, members, t)


def write(path: str, points: list[PointObj], shapes, attribution: str,
          bbox: tuple[float, float, float, float] | None, negative_ids: bool = False,
          store=None, spill_at: int = 3_000_000) -> dict:
    """Write seamark nodes, then way vertices, ways and relations.

    `shapes`: iterable of (kind, cls, wkb, tags) in output order, or a list of Merged.
    IDs are 1, 2, 3, ... per object type (Planetiler requires ascending, non-negative node
    IDs); with negative_ids they are -1, -2, -3, ... (see docs/DECISIONS.md D16)."""
    from enc2osm.store import TempStore

    own = store is None
    store = store or TempStore()
    sign = -1 if negative_ids else 1
    shapes = ((m.kind, m.cls, m.wkb, m.tags) if isinstance(m, Merged) else m for m in shapes)
    plan = Plan(len(points), shapes, store, spill_at)
    if os.path.exists(path):
        os.remove(path)
    hdr = osmium.io.Header()
    hdr.set("generator", f"enc2osm {__version__}")
    hdr.set("source", attribution)
    if bbox:
        hdr.add_box(osmium.osm.Box(osmium.osm.Location(bbox[0], bbox[1]),
                                   osmium.osm.Location(bbox[2], bbox[3])))
    shortened: dict[str, int] = {}
    w = osmium.SimpleWriter(path, header=hdr)
    try:
        for i, p in enumerate(points, 1):
            w.add_node(mutable.Node(id=sign * i, location=(p.x, p.y),
                                    tags=fit_tags(p.tags, shortened)))
        n_vertices = 0
        for nid, (qx, qy) in plan.vs.items():
            n_vertices += 1
            w.add_node(mutable.Node(id=sign * nid, location=(qx / QUANT, qy / QUANT), tags={}))
        for wid, ids, tags in store.ways():
            w.add_way(mutable.Way(id=sign * wid, nodes=[sign * n for n in ids],
                                  tags=fit_tags(tags, shortened)))
        for rid, members, tags in store.rels():
            w.add_relation(mutable.Relation(
                id=sign * rid, members=[(t, sign * r, role) for t, r, role in members],
                tags=fit_tags(tags, shortened)))
    finally:
        w.close()
        if own:
            store.close()
    return {**dict(sorted(shortened.items())),
            "seamark_nodes": len(points), "vertex_nodes": n_vertices,
            "ways": plan.n_ways, "relations": plan.n_rels}
