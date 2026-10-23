"""Phase 6 (points): seam deduplication and the dropped-object audit.

Seam dedup: points kept because they lie within the seam tolerance of their cell's effective
area may be the same physical mark as a point from a neighbouring cell. Candidate pairs are
(p, q) from different cells, at most `tol` metres apart, with the same seamark:type and either
the same non-empty seamark:name or (both unnamed) identical colour and shape tags; at least one
of the two is a seam candidate.

Duplicates with a position offset only arise where coverages overlap (different bands, or
same-band overlap). Between cells whose coverages merely touch, a mark charted in both sits at
(practically) the same position, so such pairs are only considered up to `touch_eps` metres;
a farther pair there is two different marks (merging it would lose one).

Pairs are decided greedily by distance. A pair is merged only if it is unambiguous: neither
point has another open candidate *from the same cell as its partner* within `margin` metres of
the pair's distance (a cell encodes each physical mark once, so two such candidates means we
cannot tell which one is the twin). Merged -> the higher-priority cell's version is kept.
Ambiguous -> both kept and logged. See docs/DECISIONS.md (D13).
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass

from enc2osm.pass2 import PointObj

M_PER_DEG = 111_320.0


def dist_m(a: PointObj, b: PointObj) -> float:
    """Equirectangular distance in metres (fine for <= 1 km)."""
    lat = math.radians((a.y + b.y) / 2)
    dx = (a.x - b.x) * math.cos(lat) * M_PER_DEG
    dy = (a.y - b.y) * M_PER_DEG
    return math.hypot(dx, dy)


class Grid:
    """Metric grid over lon/lat points; query returns points within `radius` metres."""

    def __init__(self, points: list[PointObj], cell_m: float):
        self.cell = cell_m
        self.idx: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.points = points
        for i, p in enumerate(points):
            self.idx[self._key(p.x, p.y)].append(i)

    def _key(self, x: float, y: float) -> tuple[int, int]:
        # x scaled at the latitude band of y; neighbours +-1 cover the cos(lat) drift locally
        return (math.floor(x * math.cos(math.radians(y)) * M_PER_DEG / self.cell),
                math.floor(y * M_PER_DEG / self.cell))

    def near(self, p: PointObj, radius: float) -> list[int]:
        kx, ky = self._key(p.x, p.y)
        r = math.ceil(radius / self.cell)
        out = []
        for ix in range(kx - r - 1, kx + r + 2):
            for iy in range(ky - r, ky + r + 1):
                for j in self.idx.get((ix, iy), ()):
                    if dist_m(p, self.points[j]) <= radius:
                        out.append(j)
        return out


def _attr(p: PointObj, attr: str) -> str | None:
    return p.tags.get(f"seamark:{p.tags.get('seamark:type')}:{attr}")


def compatible(a: PointObj, b: PointObj) -> bool:
    if a.cell == b.cell or a.tags.get("seamark:type") != b.tags.get("seamark:type"):
        return False
    na, nb = a.tags.get("seamark:name"), b.tags.get("seamark:name")
    if na or nb:
        return bool(na) and na == nb
    return _attr(a, "colour") == _attr(b, "colour") and _attr(a, "shape") == _attr(b, "shape")


@dataclass
class Decision:
    action: str  # merged | ambiguous
    kept: PointObj
    other: PointObj
    distance: float


def priority(p: PointObj) -> tuple:
    return (p.rank, p.cell)


def dedup(points: list[PointObj], tol: float, margin: float, overlaps=None,
          touch_eps: float = 1.0):
    """Returns (kept points, decisions).

    `overlaps(cell_a, cell_b) -> bool` tells whether two cells' coverages overlap (positive area);
    None means "assume they do".
    """
    points = sorted(points, key=lambda p: (p.rank, p.cell, p.cls, p.lnam, p.x, p.y))
    grid = Grid(points, max(tol, 1.0))
    edges = []
    nbr: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for i, p in enumerate(points):
        for j in grid.near(p, tol):
            if j <= i:
                continue
            q = points[j]
            if not (p.seam or q.seam) or not compatible(p, q):
                continue
            d = dist_m(p, q)
            if d > touch_eps and overlaps is not None and not overlaps(p.cell, q.cell):
                continue
            edges.append((d, i, j))
            nbr[i].append((d, j))
            nbr[j].append((d, i))
    edges.sort()

    removed: set[int] = set()
    absorbed: dict[int, set[str]] = defaultdict(set)  # cells already merged into a kept point
    decisions: list[Decision] = []
    for d, i, j in edges:
        if i in removed or j in removed:
            continue
        p, q = points[i], points[j]
        if q.cell in absorbed[i] or p.cell in absorbed[j]:
            continue
        rivals = [k for dd, k in nbr[i] if k != j and k not in removed
                  and points[k].cell == q.cell and dd <= d + margin]
        rivals += [k for dd, k in nbr[j] if k != i and k not in removed
                   and points[k].cell == p.cell and dd <= d + margin]
        if rivals:
            keep, other = (p, q) if priority(p) <= priority(q) else (q, p)
            decisions.append(Decision("ambiguous", keep, other, d))
            continue
        if priority(p) <= priority(q):
            removed.add(j)
            absorbed[i] |= {q.cell} | absorbed[j]
            decisions.append(Decision("merged", p, q, d))
        else:
            removed.add(i)
            absorbed[j] |= {p.cell} | absorbed[i]
            decisions.append(Decision("merged", q, p, d))
    kept = [p for k, p in enumerate(points) if k not in removed]
    return kept, decisions


def write_decisions(path, decisions: list[Decision]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["action", "distance_m", "seamark_type", "name", "kept_cell", "kept_lnam",
                     "kept_lon", "kept_lat", "other_cell", "other_lnam", "other_lon", "other_lat"])
        for dc in decisions:
            k, o = dc.kept, dc.other
            w.writerow([dc.action, f"{dc.distance:.1f}", k.tags.get("seamark:type"),
                        k.tags.get("seamark:name", ""), k.cell, k.lnam, f"{k.x:.7f}",
                        f"{k.y:.7f}", o.cell, o.lnam, f"{o.x:.7f}", f"{o.y:.7f}"])


def audit(dropped: list[PointObj], kept: list[PointObj], tol: float,
          name_radius: float = 1000.0) -> list[tuple[PointObj, str]]:
    """Clipped-away points without a counterpart in the output.

    Counterpart = same seamark:type within 2x tol, or same type and same non-empty name within
    `name_radius` metres.
    """
    grid = Grid(kept, max(tol, 1.0))
    missing = []
    for d in sorted(dropped, key=lambda p: (p.cell, p.cls, p.lnam)):
        typ, name = d.tags.get("seamark:type"), d.tags.get("seamark:name")
        found = None
        for j in grid.near(d, 2 * tol):
            if kept[j].tags.get("seamark:type") == typ:
                found = "type_near"
                break
        if not found and name:
            for j in grid.near(d, name_radius):
                k = kept[j]
                if k.tags.get("seamark:type") == typ and k.tags.get("seamark:name") == name:
                    found = "name"
                    break
        if not found:
            missing.append((d, "none"))
    return missing
