"""Phase 6 (lines/areas): re-join pieces that were cut apart at coverage seams.

Pieces from *different* cells with identical tags (ignoring enc:* provenance) that touch within
the seam tolerance are merged: areas by union, lines by joining at matching endpoints. The merged
feature lists all source cells in enc:cell (sorted, ';'-separated).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from osgeo import ogr

from enc2osm.inventory import polygons_only, valid
from enc2osm.pass2 import ShapeObj, lines_only


def identity(tags: dict[str, str]) -> tuple:
    return tuple(sorted((k, v) for k, v in tags.items() if not k.startswith("enc:")))


@dataclass
class Merged:
    kind: str
    cls: str
    wkb: bytes = field(repr=False)
    tags: dict[str, str]
    sources: list[ShapeObj]

    @property
    def sort_key(self) -> tuple:
        return (min(s.cell for s in self.sources), self.cls, min(s.lnam for s in self.sources))


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _provenance(sources: list[ShapeObj], base: dict[str, str]) -> dict[str, str]:
    tags = {k: v for k, v in base.items() if not k.startswith("enc:")}
    tags["enc:cell"] = ";".join(sorted({s.cell for s in sources}))
    tags["enc:band"] = ";".join(sorted({s.tags["enc:band"] for s in sources}))
    lnams = sorted({s.tags["enc:lnam"] for s in sources if s.tags.get("enc:lnam")})
    if lnams:
        tags["enc:lnam"] = ";".join(lnams)
    for k in ("enc:scamin", "enc:sordat"):
        vals = sorted({s.tags[k] for s in sources if s.tags.get(k)})
        if vals:
            tags[k] = ";".join(vals)
    return tags


def _endpoints(line: ogr.Geometry):
    n = line.GetPointCount()
    return line.GetPoint_2D(0), line.GetPoint_2D(n - 1)


def _d(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def join_lines(parts: list[tuple[str, ogr.Geometry]], tol_deg: float) -> list[ogr.Geometry]:
    """Greedily join LineStrings from different cells whose endpoints lie within tol_deg."""
    chains = [([cell], [line.GetPoint_2D(i) for i in range(line.GetPointCount())])
              for cell, line in parts]
    changed = True
    while changed:
        changed = False
        best = None
        for i in range(len(chains)):
            for j in range(i + 1, len(chains)):
                ci, cj = chains[i], chains[j]
                if set(ci[0]) & set(cj[0]):
                    continue
                a, b = ci[1], cj[1]
                for how, d in (("ee", _d(a[-1], b[0])), ("er", _d(a[-1], b[-1])),
                               ("se", _d(a[0], b[-1])), ("sr", _d(a[0], b[0]))):
                    if d <= tol_deg and (best is None or d < best[0]):
                        best = (d, i, j, how)
        if best:
            _, i, j, how = best
            a, b = chains[i][1], chains[j][1]
            if how == "ee":
                pts = a + b
            elif how == "er":
                pts = a + b[::-1]
            elif how == "se":
                pts = b + a
            else:
                pts = b[::-1] + a
            dedup = [pts[0]] + [p for k, p in enumerate(pts[1:], 1) if p != pts[k - 1]]
            chains[i] = (chains[i][0] + chains[j][0], dedup)
            del chains[j]
            changed = True
    out = []
    for _cells, pts in chains:
        ls = ogr.Geometry(ogr.wkbLineString)
        for x, y in pts:
            ls.AddPoint_2D(x, y)
        out.append(ls)
    return out


GRID_DEG = 0.05      # bucket size for the candidate search
MAX_BUCKETS = 4096   # envelopes spanning more buckets are compared against everything


def _candidate_pairs(items: list[ShapeObj], envs: list, tol_deg: float):
    """Pairs (i, j), i < j, from different cells whose envelopes (grown by tol) overlap."""
    cell = max(GRID_DEG, tol_deg * 4)
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    big: list[int] = []
    for i, (minx, maxx, miny, maxy) in enumerate(envs):
        bx0, bx1 = int((minx - tol_deg) // cell), int((maxx + tol_deg) // cell)
        by0, by1 = int((miny - tol_deg) // cell), int((maxy + tol_deg) // cell)
        if (bx1 - bx0 + 1) * (by1 - by0 + 1) > MAX_BUCKETS:
            big.append(i)
            continue
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                buckets[(bx, by)].append(i)
    cands = set()
    for idx in buckets.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                cands.add((min(idx[a], idx[b]), max(idx[a], idx[b])))
    for i in big:
        for j in range(len(items)):
            if j != i:
                cands.add((min(i, j), max(i, j)))
    for i, j in sorted(cands):
        if items[i].cell == items[j].cell:
            continue
        ei, ej = envs[i], envs[j]
        if (ei[0] - tol_deg > ej[1] or ej[0] - tol_deg > ei[1]
                or ei[2] - tol_deg > ej[3] or ej[2] - tol_deg > ei[3]):
            continue
        yield i, j


def rejoin_group(kind: str, items: list[ShapeObj], tol_deg: float, stats) -> list[Merged]:
    """Re-join one group of shapes with identical (kind, tags-without-enc)."""
    items = sorted(items, key=lambda s: (s.cell, s.cls, s.lnam, s.wkb))
    norm = polygons_only if kind == "area" else lines_only
    geoms = [norm(ogr.CreateGeometryFromWkb(s.wkb)) for s in items]
    envs = [g.GetEnvelope() for g in geoms]
    uf = _UF(len(items))
    for i, j in _candidate_pairs(items, envs, tol_deg):
        if uf.find(i) != uf.find(j) and geoms[i].Distance(geoms[j]) <= tol_deg:
            uf.union(i, j)
    comps: dict[int, list[int]] = defaultdict(list)
    for i in range(len(items)):
        comps[uf.find(i)].append(i)
    out = []
    for idx in comps.values():
        srcs = [items[i] for i in idx]
        if len(idx) == 1:
            out.append(Merged(kind, srcs[0].cls, srcs[0].wkb, dict(srcs[0].tags), srcs))
            continue
        stats[f"rejoined_{kind}_pieces"] += len(idx)
        stats[f"rejoined_{kind}_features"] += 1
        if kind == "area":
            coll = ogr.Geometry(ogr.wkbMultiPolygon)
            for i in idx:
                g = geoms[i]
                for k in range(g.GetGeometryCount()):
                    coll.AddGeometry(g.GetGeometryRef(k))
            merged = polygons_only(valid(coll.UnionCascaded()))
            out.append(Merged(kind, srcs[0].cls, bytes(merged.ExportToWkb()),
                              _provenance(srcs, srcs[0].tags), srcs))
        else:
            parts = []
            for i in idx:
                ml = lines_only(geoms[i])
                for k in range(ml.GetGeometryCount()):
                    parts.append((items[i].cell, ml.GetGeometryRef(k).Clone()))
            ml = ogr.Geometry(ogr.wkbMultiLineString)
            for ls in join_lines(parts, tol_deg):
                ml.AddGeometry(ls)
            out.append(Merged(kind, srcs[0].cls, bytes(ml.ExportToWkb()),
                              _provenance(srcs, srcs[0].tags), srcs))
    return out


def rejoin(shapes: list[ShapeObj], tol_deg: float) -> tuple[list[Merged], dict]:
    """In-memory convenience wrapper (tests): group, re-join, sort."""
    stats = defaultdict(int)
    groups: dict[tuple, list[ShapeObj]] = defaultdict(list)
    for s in shapes:
        groups[(s.kind, identity(s.tags))].append(s)
    out: list[Merged] = []
    for (kind, _ident), items in sorted(groups.items(), key=lambda kv: kv[0]):
        out.extend(rejoin_group(kind, items, tol_deg, stats))
    out.sort(key=lambda m: m.sort_key)
    return out, dict(stats)


def rejoin_store(store, tol_deg: float) -> dict:
    """Streaming variant: read groups from the temp store, write merged shapes back to it."""
    stats = defaultdict(int)
    for kind, items in store.groups():
        for m in rejoin_group(kind, items, tol_deg, stats):
            store.add_merged(m.sort_key, m.kind, m.cls, m.wkb, m.tags)
    return dict(stats)
