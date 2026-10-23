"""Pass 1, part 2: resolve overlapping coverages ("best scale wins").

Cells are visited in priority order; each gets what is left of its coverage
after removing everything already claimed by higher-priority cells:

    effective[cell] = coverage[cell] − mask
    mask            = mask ∪ coverage[cell]

The mask is a list of polygons with a uniform grid index on their envelopes,
so a cell is only differenced against the mask parts near it.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass

from osgeo import ogr

from enc2osm.inventory import CellInfo, polygons_only, valid

log = logging.getLogger(__name__)

M_PER_DEG = 111_320.0


def priority_key(c: CellInfo) -> tuple:
    """Sort key, highest priority first: band ↓, scale ↑ (larger scale), issue date ↓, name."""
    return (-c.band, c.cscale, _neg_date(c.issue_date), c.name)


def _neg_date(d: str) -> int:
    try:
        return -int(d)
    except ValueError:
        return 0


def ordered(cells: list[CellInfo]) -> list[CellInfo]:
    return sorted(cells, key=priority_key)


def m_to_deg(meters: float, max_abs_lat: float) -> float:
    """Meters → degrees using the cell's max |lat| (over-buffers in latitude: conservative)."""
    return meters / (M_PER_DEG * math.cos(math.radians(min(max_abs_lat, 89.0))))


def m2_to_deg2(m2: float, lat: float) -> float:
    return m2 / (M_PER_DEG * M_PER_DEG * math.cos(math.radians(min(abs(lat), 89.0))))


@dataclass
class Effective:
    name: str
    rank: int  # 0 = highest priority
    wkb: bytes
    slivers_dropped: int

    @property
    def geom(self) -> ogr.Geometry:
        return ogr.CreateGeometryFromWkb(self.wkb)


class Mask:
    def __init__(self, grid_deg: float = 0.5):
        self.grid = grid_deg
        self.parts: list[ogr.Geometry] = []
        self.index: dict[tuple[int, int], list[int]] = defaultdict(list)

    def _keys(self, env):
        minx, maxx, miny, maxy = env
        g = self.grid
        for ix in range(math.floor(minx / g), math.floor(maxx / g) + 1):
            for iy in range(math.floor(miny / g), math.floor(maxy / g) + 1):
                yield ix, iy

    def add(self, geom: ogr.Geometry) -> None:
        for i in range(geom.GetGeometryCount()):
            part = geom.GetGeometryRef(i).Clone()
            n = len(self.parts)
            self.parts.append(part)
            for k in self._keys(part.GetEnvelope()):
                self.index[k].append(n)

    def near(self, env) -> ogr.Geometry | None:
        ids = sorted({i for k in self._keys(env) for i in self.index.get(k, ())})
        minx, maxx, miny, maxy = env
        coll = ogr.Geometry(ogr.wkbMultiPolygon)
        for i in ids:
            e = self.parts[i].GetEnvelope()
            if e[1] < minx or e[0] > maxx or e[3] < miny or e[2] > maxy:
                continue
            coll.AddGeometry(self.parts[i])
        if coll.IsEmpty():
            return None
        return valid(coll.UnionCascaded())


def drop_slivers(geom: ogr.Geometry, min_m2: float) -> tuple[ogr.Geometry, int]:
    out = ogr.Geometry(ogr.wkbMultiPolygon)
    dropped = 0
    for i in range(geom.GetGeometryCount()):
        p = geom.GetGeometryRef(i)
        minx, maxx, miny, maxy = p.GetEnvelope()
        if p.GetArea() < m2_to_deg2(min_m2, (miny + maxy) / 2):
            dropped += 1
        else:
            out.AddGeometry(p)
    return out, dropped


def resolve(cells: list[CellInfo], sliver_m2: float = 10.0,
            grid_deg: float = 0.5) -> dict[str, Effective]:
    mask = Mask(grid_deg)
    result: dict[str, Effective] = {}
    for rank, c in enumerate(ordered(cells)):
        cov = c.coverage
        near = mask.near(cov.GetEnvelope())
        eff = cov if near is None else polygons_only(valid(cov.Difference(near)))
        eff, dropped = drop_slivers(eff, sliver_m2)
        if dropped:
            log.debug("%s: dropped %d sliver(s) below %s m²", c.name, dropped, sliver_m2)
        result[c.name] = Effective(c.name, rank, bytes(eff.ExportToWkb()), dropped)
        mask.add(cov)
    return result
