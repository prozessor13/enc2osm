"""Phase 5: aggregated S-57 object -> OSM seamark tags (driven by enc2osm/mapping/*.yaml)."""

from __future__ import annotations

import re
from collections import Counter

from enc2osm.aggregate import Aggregate
from enc2osm.extract import Feature
from enc2osm.inventory import CellInfo
from enc2osm.mapping import Mapping

_SIGGRP = re.compile(r"^\(([^()]*)\)$")


def fmt_number(v) -> str:
    v = float(v)
    if v == int(v):
        return str(int(v))
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _codes(v) -> list[int] | None:
    vals = v if isinstance(v, list) else [v]
    try:
        return [int(str(x).strip()) for x in vals]
    except ValueError:
        return None


def _raw(v) -> str:
    return ",".join(str(x) for x in v) if isinstance(v, list) else str(v)


class TagBuilder:
    """Collects tags for one object; a key set twice with different values is dropped."""

    def __init__(self, mapping: Mapping, stats: Counter, keep_raw: bool):
        self.m, self.stats, self.keep_raw = mapping, stats, keep_raw
        self.tags: dict[str, str] = {}
        self.conflicts: set[str] = set()

    def put(self, key: str, value: str) -> None:
        if key in self.conflicts:
            return
        old = self.tags.get(key)
        if old is not None and old != value:
            del self.tags[key]
            self.conflicts.add(key)
            self.stats[f"conflict:{key}"] += 1
        else:
            self.tags[key] = value

    def unmapped(self, acr: str, raw, reason: str) -> None:
        self.stats[f"{reason}:{acr}"] += 1
        if self.keep_raw:
            self.put(f"enc:{acr}", _raw(raw))

    def convert(self, acr: str, v) -> str | None:
        a = self.m.attributes[acr]
        kind = a["kind"]
        if kind in ("enum", "list"):
            codes = _codes(v)
            if codes is None or (kind == "enum" and len(codes) != 1):
                self.unmapped(acr, v, "unmapped_value")
                return None
            vals = [self.m.value(acr, c) for c in codes]
            if any(x is None for x in vals):
                # never emit a partial list: a dropped element changes the meaning
                for c, x in zip(codes, vals, strict=True):
                    if x is None:
                        self.stats[f"unmapped_value:{acr}={c}"] += 1
                if self.keep_raw:
                    self.put(f"enc:{acr}", _raw(v))
                return None
            return ";".join(vals)
        if kind == "text":
            return str(v)
        if kind in ("number", "depth", "height"):
            try:
                return fmt_number(v)
            except (TypeError, ValueError):
                self.unmapped(acr, v, "bad_number")
                return None
        if kind == "int":
            try:
                return str(int(float(v)))
            except (TypeError, ValueError):
                self.unmapped(acr, v, "bad_number")
                return None
        if kind == "siggrp":
            mt = _SIGGRP.match(str(v).strip())
            if mt is None:
                self.unmapped(acr, v, "unmapped_value")
                return None
            return mt.group(1) or None
        raise AssertionError(kind)

    def add_feature(self, f: Feature, prefix: str, system: bool) -> None:
        for acr in sorted(f.attrs):
            v = f.attrs[acr]
            a = self.m.attributes.get(acr)
            if a is None:
                self.unmapped(acr, v, "unmapped_attr")
                continue
            if a["kind"] == "meta":
                continue
            if acr == "MARSYS" and not system:
                self.stats["marsys_ignored"] += 1
                continue
            val = self.convert(acr, v)
            if val is None:
                continue
            if a["key"] == "name":
                continue  # names are resolved per object, see build()
            self.put(f"{prefix}{a['key']}", val)


def light_type(lights: list[Feature], mapping: Mapping) -> str:
    rule = mapping.rules["light"]
    ranges = []
    for f in lights:
        try:
            ranges.append(float(f.attrs["VALNMR"]))
        except (KeyError, TypeError, ValueError):
            pass
    return rule["major"] if ranges and max(ranges) >= rule["major_min_range"] else rule["minor"]


def build(agg: Aggregate, cell: CellInfo, mapping: Mapping, stats: Counter,
          keep_raw: bool = False) -> dict[str, str]:
    tb = TagBuilder(mapping, stats, keep_raw)
    m = agg.master
    if m is not None:
        obj = mapping.objects[m.cls]
        stype = obj["type"]
        tb.add_feature(m, f"seamark:{stype}:", bool(obj.get("system")))
    else:
        obj = mapping.objects[agg.standalone_cls]
        stype = obj["standalone"]
        if stype == "light":
            stype = light_type([s for s in agg.slaves if s.cls == "LIGHTS"], mapping)
    tb.put("seamark:type", stype)

    by_cls: dict[str, list[Feature]] = {}
    for s in agg.slaves:
        by_cls.setdefault(s.cls, []).append(s)
    for cls, group in by_cls.items():
        key = mapping.objects[cls]["slave_key"]
        if cls == "LIGHTS":
            sectored = any("SECTR1" in s.attrs or "SECTR2" in s.attrs for s in group)
            numbered = len(group) > 1 or sectored
        else:
            numbered = len(group) > 1 and len({_sig(s) for s in group}) > 1
            if len(group) > 1 and not numbered:
                group = group[:1]  # identical copies, e.g. the same daymark on both faces
                stats[f"identical_slaves_merged:{cls}"] += 1
        for i, s in enumerate(group, 1):
            tb.add_feature(s, f"seamark:{key}:{i}:" if numbered else f"seamark:{key}:", False)

    names = [f.attrs["OBJNAM"] for f in ([m] if m is not None else []) + agg.slaves
             if f.attrs.get("OBJNAM")]
    if names:
        tb.put("seamark:name", str(names[0]))
        if len(set(names)) > 1:
            stats["slave_name_dropped"] += 1

    p = agg.primary
    tb.tags["enc:cell"] = cell.name
    tb.tags["enc:band"] = str(cell.band)
    if p.lnam:
        tb.tags["enc:lnam"] = p.lnam
    if p.attrs.get("SCAMIN") is not None:
        tb.tags["enc:scamin"] = str(int(float(p.attrs["SCAMIN"])))
    if p.attrs.get("SORDAT"):
        tb.tags["enc:sordat"] = str(p.attrs["SORDAT"])
    return tb.tags


def _sig(f: Feature) -> tuple:
    return tuple(sorted((k, _raw(v)) for k, v in f.attrs.items()
                        if k not in ("SCAMIN", "SCAMAX", "SORDAT", "SORIND", "RECDAT", "RECIND")))
