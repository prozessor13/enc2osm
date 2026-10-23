"""Phase 3: read the in-scope features of one cell, normalize units, inherit MARSYS."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from osgeo import ogr

from enc2osm import s57
from enc2osm.mapping import Mapping

log = logging.getLogger(__name__)

# OGR S-57 fields that are record bookkeeping, not object attributes.
RECORD_FIELDS = {"RCID", "PRIM", "GRUP", "OBJL", "RVER", "AGEN", "FIDN", "FIDS",
                 "LNAM", "LNAM_REFS", "FFPT_RIND"}

# DSPM_DUNI / DSPM_HUNI (IHO S-57 Ed. 3.1, Part 3, DSPM field). Factor to metres; None = known
# unit whose encoding we do not convert (see docs/OPEN_QUESTIONS.md).
DEPTH_UNITS = {1: 1.0, 2: None, 3: 0.3048, 4: 1.8288}  # m, fathoms+feet, feet, fathoms+fractions
HEIGHT_UNITS = {1: 1.0, 2: 0.3048}  # m, feet

GEOM_KIND = {
    ogr.wkbPoint: "point", ogr.wkbLineString: "line", ogr.wkbMultiLineString: "line",
    ogr.wkbPolygon: "area", ogr.wkbMultiPolygon: "area",
}


@dataclass
class Feature:
    cls: str
    lnam: str
    kind: str  # point | line | area
    wkb: bytes = field(repr=False)
    attrs: dict
    refs: list[tuple[str, int]]  # (LNAM, FFPT_RIND)
    x: float | None = None
    y: float | None = None

    @property
    def geom(self) -> ogr.Geometry:
        return ogr.CreateGeometryFromWkb(self.wkb)


def _clean(v):
    if isinstance(v, list):
        v = [str(x).strip() for x in v if x is not None and str(x).strip() != ""]
        return v or None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def convert_units(attrs: dict, mapping: Mapping, duni, huni, stats: Counter) -> dict:
    """Convert depth/height attributes to metres; drop them if the unit is unknown."""
    out = {}
    for acr, val in attrs.items():
        kind = mapping.attributes.get(acr, {}).get("kind")
        if kind in ("depth", "height"):
            table = DEPTH_UNITS if kind == "depth" else HEIGHT_UNITS
            unit = duni if kind == "depth" else huni
            factor = table.get(unit)
            if factor is None:
                stats[f"unit_unknown:{acr}:{kind[0].upper()}UNI={unit}"] += 1
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                stats[f"bad_number:{acr}"] += 1
                continue
            val = val if factor == 1.0 else round(val * factor, 2)
        out[acr] = val
    return out


def read_nsys(ds: ogr.DataSource) -> list[tuple[ogr.Geometry, int]]:
    lyr = ds.GetLayerByName("M_NSYS")
    out = []
    if lyr is None:
        return out
    for f in lyr:
        g, marsys = f.GetGeometryRef(), f.GetField("MARSYS") if f.GetFieldIndex("MARSYS") >= 0 \
            else None
        if g is not None and marsys is not None:
            out.append((g.Clone(), int(marsys)))
    return out


def inherit_marsys(feat: Feature, nsys: list[tuple[ogr.Geometry, int]], stats: Counter) -> None:
    if "MARSYS" in feat.attrs or feat.kind != "point" or not nsys:
        return
    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint_2D(feat.x, feat.y)
    found = {m for g, m in nsys if g.Intersects(pt)}
    if len(found) == 1:
        feat.attrs["MARSYS"] = found.pop()
        stats["marsys_inherited"] += 1
    elif len(found) > 1:
        stats["marsys_conflict"] += 1


def read_features(path, mapping: Mapping, classes: list[str], duni, huni,
                  stats: Counter) -> list[Feature]:
    ds = s57.open_cell(path)
    nsys = read_nsys(ds)
    out: list[Feature] = []
    for cls in classes:
        lyr = ds.GetLayerByName(cls)
        if lyr is None:
            continue
        allowed = set(mapping.objects[cls]["geometry"])
        for f in lyr:
            g = f.GetGeometryRef()
            kind = GEOM_KIND.get(ogr.GT_Flatten(g.GetGeometryType())) if g is not None else None
            stats[f"read:{cls}"] += 1
            if kind is None or kind not in allowed:
                stats[f"skipped_geometry:{cls}:{kind}"] += 1
                continue
            raw = {}
            for k, v in f.items().items():
                if k in RECORD_FIELDS:
                    continue
                v = _clean(v)
                if v is not None:
                    raw[k] = v
            refs = list(zip(f.GetField("LNAM_REFS") or [], f.GetField("FFPT_RIND") or [],
                            strict=False))
            feat = Feature(cls=cls, lnam=f.GetField("LNAM") or "", kind=kind,
                           wkb=bytes(g.ExportToWkb()),
                           attrs=convert_units(raw, mapping, duni, huni, stats), refs=refs)
            if kind == "point":
                feat.x, feat.y = g.GetX(), g.GetY()
            if mapping.objects[cls].get("system"):
                inherit_marsys(feat, nsys, stats)
            out.append(feat)
    out.sort(key=lambda f: (f.cls, f.lnam, f.wkb))
    return out
