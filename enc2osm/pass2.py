"""Pass 2: per cell — read, aggregate, map, clip. Runs in worker processes; returns plain data."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from osgeo import ogr

from enc2osm import aggregate, extract, tags
from enc2osm.coverage import Effective, m_to_deg
from enc2osm.inventory import CellInfo
from enc2osm.mapping import Mapping

log = logging.getLogger(__name__)


@dataclass
class Options:
    scope: str = "v1"
    seam_tolerance: float = 50.0  # metres
    keep_raw: bool = False
    bbox: tuple[float, float, float, float] | None = None
    sliver_m2: float = 10.0


@dataclass
class PointObj:
    cell: str
    rank: int
    cls: str
    lnam: str
    x: float
    y: float
    tags: dict[str, str]
    seam: bool = False  # within seam tolerance of the effective-area boundary

    @property
    def key(self) -> tuple:
        return (self.cell, self.cls, self.lnam, self.x, self.y)


@dataclass
class ShapeObj:
    """A clipped line or area (v2)."""
    cell: str
    rank: int
    cls: str
    lnam: str
    kind: str  # line | area
    wkb: bytes = field(repr=False)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class CellResult:
    cell: str
    stats: Counter
    points: list[PointObj]
    dropped: list[PointObj]  # clipped away: lie in a higher-priority cell's area
    shapes: list[ShapeObj]


def bbox_geom(bbox) -> ogr.Geometry:
    minx, miny, maxx, maxy = bbox
    return ogr.CreateGeometryFromWkt(
        f"POLYGON(({minx} {miny},{maxx} {miny},{maxx} {maxy},{minx} {maxy},{minx} {miny}))")


def tolerance_deg(cell: CellInfo, meters: float) -> float:
    minx, miny, maxx, maxy = cell.bbox
    return m_to_deg(meters, max(abs(miny), abs(maxy)))


class PointClipper:
    """Keep points within the effective area buffered by the seam tolerance; flag those within
    the tolerance of its boundary (inside or outside) as seam candidates."""

    def __init__(self, effg: ogr.Geometry, tol_deg: float):
        empty = effg.IsEmpty()
        self.outer = effg if empty else effg.Buffer(tol_deg)
        self.inner = effg if empty else effg.Buffer(-tol_deg)

    def status(self, x: float, y: float) -> str:
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AddPoint_2D(x, y)
        if self.outer.IsEmpty() or not self.outer.Intersects(pt):
            return "drop"
        return "seam" if self.inner.IsEmpty() or not self.inner.Contains(pt) else "keep"


def process_cell(cell: CellInfo, eff: Effective, mapping: Mapping, opts: Options) -> CellResult:
    stats: Counter = Counter()
    feats = extract.read_features(cell.path, mapping, mapping.classes(opts.scope), cell.duni,
                                  cell.huni, stats)
    aggs = aggregate.aggregate(feats, mapping, stats)

    effg = eff.geom
    clipper = PointClipper(effg, tolerance_deg(cell, opts.seam_tolerance))
    bbox = bbox_geom(opts.bbox) if opts.bbox else None
    bbox_env = opts.bbox

    points, dropped, shapes = [], [], []
    for agg in aggs:
        t = tags.build(agg, cell, mapping, stats, opts.keep_raw)
        if agg.kind == "point":
            p = agg.primary
            obj = PointObj(cell.name, eff.rank, agg.cls, agg.lnam, p.x, p.y, t)
            if bbox is not None and not (bbox_env[0] <= p.x <= bbox_env[2]
                                         and bbox_env[1] <= p.y <= bbox_env[3]):
                stats["outside_bbox"] += 1
                continue
            status = clipper.status(p.x, p.y)
            if status == "drop":
                # the audit only needs type and name; keep the rest out of memory
                obj.tags = {k: t[k] for k in ("seamark:type", "seamark:name") if k in t}
                dropped.append(obj)
                stats["points_clipped"] += 1
                continue
            obj.seam = status == "seam"
            stats["points_kept"] += 1
            stats["seam_candidates"] += obj.seam
            points.append(obj)
        else:
            shapes.extend(clip_shape(agg, t, cell, eff, effg, bbox, opts, stats))
    return CellResult(cell.name, stats, points, dropped, shapes)


def clip_shape(agg, t, cell, eff, effg, bbox, opts, stats) -> list[ShapeObj]:
    """Lines/areas: Intersection with the effective area (no buffer); drop empties/slivers."""
    from enc2osm.coverage import m2_to_deg2
    from enc2osm.inventory import polygons_only, valid

    g = valid(agg.primary.geom)
    clip = effg if bbox is None else effg.Intersection(bbox)
    if clip.IsEmpty():
        stats["shapes_clipped"] += 1
        return []
    res = g.Intersection(clip)
    if agg.kind == "area":
        res = polygons_only(valid(res))
        minx, maxx, miny, maxy = res.GetEnvelope() if not res.IsEmpty() else (0, 0, 0, 0)
        keep = ogr.Geometry(ogr.wkbMultiPolygon)
        for i in range(res.GetGeometryCount()):
            part = res.GetGeometryRef(i)
            if part.GetArea() >= m2_to_deg2(opts.sliver_m2, (miny + maxy) / 2):
                keep.AddGeometry(part)
        res = keep
    else:
        res = lines_only(res)
    if res.IsEmpty():
        stats["shapes_clipped"] += 1
        return []
    stats["shapes_kept"] += 1
    return [ShapeObj(cell.name, eff.rank, agg.cls, agg.lnam, agg.kind, bytes(res.ExportToWkb()),
                     t)]


def lines_only(g: ogr.Geometry) -> ogr.Geometry:
    out = ogr.Geometry(ogr.wkbMultiLineString)
    if g is None or g.IsEmpty():
        return out
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbLineString:
        out.AddGeometry(g)
    elif t in (ogr.wkbMultiLineString, ogr.wkbGeometryCollection):
        for i in range(g.GetGeometryCount()):
            sub = lines_only(g.GetGeometryRef(i))
            for j in range(sub.GetGeometryCount()):
                out.AddGeometry(sub.GetGeometryRef(j))
    return out
