"""Pass 1, part 1: read DSID + M_COVR of every cell (cheap)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from osgeo import ogr

from enc2osm import s57

log = logging.getLogger(__name__)


@dataclass
class CellInfo:
    name: str
    path: str
    band: int
    edition: int
    update: int
    issue_date: str
    cscale: int
    duni: int | None
    huni: int | None
    coverage_wkb: bytes = field(repr=False)
    bbox: tuple[float, float, float, float]  # minx, miny, maxx, maxy

    @property
    def coverage(self) -> ogr.Geometry:
        return ogr.CreateGeometryFromWkb(self.coverage_wkb)

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("coverage_wkb")
        d["coverage_area_deg2"] = round(self.coverage.GetArea(), 8)
        return d


@dataclass
class Skipped:
    path: str
    reason: str


def _int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def valid(g: ogr.Geometry) -> ogr.Geometry:
    if g is not None and not g.IsValid():
        g = g.MakeValid()
    return g


def polygons_only(g: ogr.Geometry | None) -> ogr.Geometry:
    """Return the polygonal part of `g` as a MultiPolygon (empty if none)."""
    out = ogr.Geometry(ogr.wkbMultiPolygon)
    if g is None or g.IsEmpty():
        return out
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbPolygon:
        out.AddGeometry(g)
    elif t in (ogr.wkbMultiPolygon, ogr.wkbGeometryCollection):
        for i in range(g.GetGeometryCount()):
            sub = polygons_only(g.GetGeometryRef(i))
            for j in range(sub.GetGeometryCount()):
                out.AddGeometry(sub.GetGeometryRef(j))
    return out


def read_coverage(ds: ogr.DataSource) -> ogr.Geometry | None:
    """Union of M_COVR CATCOV=1 minus CATCOV=2 (no-coverage) polygons; None if unusable."""
    lyr = ds.GetLayerByName("M_COVR")
    if lyr is None:
        return None
    cov, nocov = ogr.Geometry(ogr.wkbMultiPolygon), ogr.Geometry(ogr.wkbMultiPolygon)
    for f in lyr:
        g = f.GetGeometryRef()
        if g is None:
            continue
        target = {1: cov, 2: nocov}.get(f.GetField("CATCOV"))
        if target is None:
            continue
        parts = polygons_only(valid(g.Clone()))
        for j in range(parts.GetGeometryCount()):
            target.AddGeometry(parts.GetGeometryRef(j))
    if cov.IsEmpty():
        return None
    union = polygons_only(valid(cov.UnionCascaded()))
    if not nocov.IsEmpty():
        union = polygons_only(valid(union.Difference(valid(nocov.UnionCascaded()))))
    return None if union.IsEmpty() else union


def read_cell(path: Path) -> CellInfo:
    ds = s57.open_cell(path)
    dsid = ds.GetLayerByName("DSID")
    f = dsid.GetNextFeature() if dsid is not None else None
    if f is None:
        raise RuntimeError("no DSID record")
    name = (f.GetField("DSID_DSNM") or path.name).rsplit(".", 1)[0].upper()
    band = _int(f.GetField("DSID_INTU"))
    if not 1 <= band <= 6:
        raise RuntimeError(f"invalid usage band DSID_INTU={f.GetField('DSID_INTU')}")
    cscale = _int(f.GetField("DSPM_CSCL"))
    if cscale <= 0:
        raise RuntimeError("missing compilation scale DSPM_CSCL")
    cov = read_coverage(ds)
    if cov is None:
        raise RuntimeError("no usable M_COVR (CATCOV=1) coverage")
    minx, maxx, miny, maxy = cov.GetEnvelope()
    return CellInfo(
        name=name, path=str(path), band=band,
        edition=_int(f.GetField("DSID_EDTN")), update=_int(f.GetField("DSID_UPDN")),
        issue_date=f.GetField("DSID_ISDT") or "", cscale=cscale,
        duni=f.GetField("DSPM_DUNI"), huni=f.GetField("DSPM_HUNI"),
        coverage_wkb=bytes(cov.ExportToWkb()), bbox=(minx, miny, maxx, maxy),
    )


def build(inputs: list[str]) -> tuple[list[CellInfo], list[Skipped]]:
    cells: dict[str, CellInfo] = {}
    skipped: list[Skipped] = []
    for path in s57.discover(inputs):
        try:
            info = read_cell(path)
        except RuntimeError as e:
            log.warning("skipping %s: %s", path, e)
            skipped.append(Skipped(str(path), str(e)))
            continue
        old = cells.get(info.name)
        if old is not None:
            keep, drop = sorted([old, info], key=lambda c: (c.edition, c.update, c.path))[::-1]
            log.warning("cell %s given twice: keeping %s (ed %d upd %d), ignoring %s",
                        info.name, keep.path, keep.edition, keep.update, drop.path)
            skipped.append(Skipped(drop.path, f"duplicate of {keep.path} (older edition/update)"))
            info = keep
        cells[info.name] = info
    return [cells[k] for k in sorted(cells)], skipped


def run(args) -> int:
    cells, skipped = build(args.inputs)
    if args.json:
        print(json.dumps({"cells": [c.summary() for c in cells],
                          "skipped": [asdict(s) for s in skipped]}, indent=1))
        return 0
    print(f"{'cell':10} {'band':>4} {'ed':>3} {'upd':>3} {'issued':8} {'scale':>9} "
          f"{'DUNI':>4} {'HUNI':>4}  bbox")
    for c in cells:
        bb = ",".join(f"{v:.4f}" for v in c.bbox)
        print(f"{c.name:10} {c.band:4d} {c.edition:3d} {c.update:3d} {c.issue_date:8} "
              f"{c.cscale:9d} {c.duni!s:>4} {c.huni!s:>4}  {bb}")
    for s in skipped:
        print(f"SKIPPED {s.path}: {s.reason}")
    return 0
