"""``enc2osm lnam-check``: how often does the same LNAM occur in more than one cell?

Informational only — no design decision depends on the result (cross-cell
dedup is done by coverage clipping + seam matching, never by LNAM).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from enc2osm import s57

log = logging.getLogger(__name__)

CLASSES = ("BOYLAT", "BOYCAR", "BOYSAW", "BOYSPP", "BOYISD",
           "BCNLAT", "BCNCAR", "BCNSAW", "BCNSPP", "BCNISD", "LIGHTS")


def collect(paths) -> dict[str, dict[str, set[str]]]:
    """class -> LNAM -> set of cell names."""
    seen: dict[str, dict[str, set[str]]] = {c: defaultdict(set) for c in CLASSES}
    for path in paths:
        try:
            ds = s57.open_cell(path)
        except RuntimeError as e:
            log.warning("skipping %s: %s", path, e)
            continue
        cell = path.stem.upper()
        for cls in CLASSES:
            lyr = ds.GetLayerByName(cls)
            if lyr is None:
                continue
            for f in lyr:
                lnam = f.GetField("LNAM")
                if lnam:
                    seen[cls][lnam].add(cell)
        ds = None
    return seen


def summarize(seen) -> dict:
    out = {}
    for cls in CLASSES:
        lnams = seen[cls]
        multi = {k: v for k, v in lnams.items() if len(v) > 1}
        out[cls] = {"lnams": len(lnams), "in_multiple_cells": len(multi),
                    "example": sorted(sorted(v) for v in multi.values())[:3]}
    tot = sum(o["lnams"] for o in out.values())
    mul = sum(o["in_multiple_cells"] for o in out.values())
    out["_total"] = {"lnams": tot, "in_multiple_cells": mul,
                     "share": round(mul / tot, 4) if tot else 0.0}
    return out


def run(args) -> int:
    paths = s57.discover(args.inputs)
    res = summarize(collect(paths))
    res["_total"]["cells"] = len(paths)
    if args.json:
        print(json.dumps(res, indent=1, sort_keys=True))
        return 0
    print(f"{'class':8} {'LNAMs':>8} {'>1 cell':>8}")
    for cls in CLASSES:
        print(f"{cls:8} {res[cls]['lnams']:8d} {res[cls]['in_multiple_cells']:8d}")
    t = res["_total"]
    print(f"{'total':8} {t['lnams']:8d} {t['in_multiple_cells']:8d}  ({t['share']:.1%}), "
          f"{t['cells']} cells")
    return 0
