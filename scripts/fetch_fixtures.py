#!/usr/bin/env python3
"""Download NOAA ENC test fixtures, selecting cells by bounding box.

Catalog: https://charts.noaa.gov/ENCs/ENCProdCat.xml (one <cell> per ENC with
<status>, <edtn>, <updn>, <cscale>, <zipfile_location> and coverage panels
<cov><panel><vertex><lat/><long/></vertex>…). Cancelled cells carry no
coverage and are skipped. Download URL pattern (from the catalog itself):
https://www.charts.noaa.gov/ENCs/<CELL>.zip, containing ENC_ROOT/<CELL>/<CELL>.000
plus update files .001, .002, …

Selection uses the catalog panels intersected with the bbox (OGR), so a cell
is chosen if any of its coverage panels touches the region — in every band.

Usage (inside the project image):
    python scripts/fetch_fixtures.py small
    python scripts/fetch_fixtures.py medium
    python scripts/fetch_fixtures.py --bbox -122.52,37.78,-122.38,37.84 --list
    python3 scripts/fetch_fixtures.py --all --refresh-catalog   # every active cell, no GDAL needed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

CATALOG_URL = "https://charts.noaa.gov/ENCs/ENCProdCat.xml"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"

# Region presets. See docs/DECISIONS.md (D-fixtures) for why these boxes.
REGIONS = {
    # San Francisco: Golden Gate, city front, Alcatraz, Treasure Island.
    "small": (-122.53, 37.78, -122.36, 37.85),
    # Puget Sound: Admiralty Inlet to Tacoma, incl. Seattle and Bremerton.
    "medium": (-122.75, 47.25, -122.25, 48.00),
}

S57_FILE = re.compile(r"^[A-Z0-9]{8}\.\d{3}$", re.IGNORECASE)


def fetch(url: str, dest: Path, tries: int = 3) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            break
        except OSError:
            if attempt == tries:
                raise
            time.sleep(5 * attempt)
    tmp.rename(dest)
    return dest


def load_catalog(refresh: bool) -> list[dict]:
    path = CACHE / "ENCProdCat.xml"
    if refresh or not path.exists():
        fetch(CATALOG_URL, path)
    cells = []
    for _ev, el in ET.iterparse(path, events=("end",)):
        if el.tag != "cell":
            continue
        rec = {k: (el.findtext(k) or "").strip()
               for k in ("name", "lname", "cscale", "status", "edtn", "updn", "isdt",
                         "zipfile_location", "zipfile_size")}
        panels = []
        for panel in el.iter("panel"):
            ring = [(float(v.findtext("long")), float(v.findtext("lat")))
                    for v in panel.iter("vertex")]
            if len(ring) >= 4:
                panels.append(ring)
        rec["panels"] = panels
        el.clear()
        if rec["status"] == "Active" and panels:
            cells.append(rec)
    return cells


def panel_geom(panels: list) -> ogr.Geometry:
    from osgeo import ogr  # only needed for bbox selection

    multi = ogr.Geometry(ogr.wkbMultiPolygon)
    for ring in panels:
        r = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in ring:
            r.AddPoint_2D(x, y)
        r.CloseRings()
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(r)
        multi.AddGeometry(poly)
    return multi


def select(cells: list[dict], bbox: tuple[float, float, float, float]) -> list[dict]:
    from osgeo import ogr

    minx, miny, maxx, maxy = bbox
    box = ogr.CreateGeometryFromWkt(
        f"POLYGON(({minx} {miny},{maxx} {miny},{maxx} {maxy},{minx} {maxy},{minx} {miny}))")
    out = [c for c in cells if panel_geom(c["panels"]).Intersects(box)]
    return sorted(out, key=lambda c: c["name"])


def safe_extract(zpath: Path, cell: str, dest: Path) -> list[str]:
    """Extract only S-57 data files of `cell`, flattening paths (no traversal possible)."""
    written = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            base = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
            if info.is_dir() or not S57_FILE.match(base) or not base.upper().startswith(cell):
                continue
            target = dest / cell / base.upper()
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as f:
                f.write(src.read())
            written.append(base.upper())
    return sorted(written)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("region", nargs="?", choices=sorted(REGIONS))
    ap.add_argument("--bbox", help="minx,miny,maxx,maxy (overrides region)")
    ap.add_argument("--all", action="store_true", help="every active cell of the catalog")
    ap.add_argument("--out", help="output directory (default fixtures/<region>)")
    ap.add_argument("--list", action="store_true", help="only list the selected cells")
    ap.add_argument("--refresh-catalog", action="store_true")
    args = ap.parse_args()

    if args.all:
        bbox = None
    elif args.bbox:
        bbox = tuple(float(v) for v in args.bbox.split(","))
    elif args.region:
        bbox = REGIONS[args.region]
    else:
        ap.error("give a region, --bbox or --all")
    default_out = ROOT / "tests" / "data" / "small" if args.region == "small" else \
        ROOT / "fixtures" / ("all" if args.all else args.region or "custom")  # small: committed
    out = Path(args.out) if args.out else default_out

    cells = load_catalog(args.refresh_catalog)
    sel = sorted(cells, key=lambda c: c["name"]) if bbox is None else select(cells, bbox)
    total = sum(int(c["zipfile_size"] or 0) for c in sel)
    for c in sel:
        print(f"{c['name']}  band={c['name'][2]}  1:{c['cscale']:>8}  ed={c['edtn']}.{c['updn']}"
              f"  {int(c['zipfile_size'] or 0) / 1e6:6.2f} MB  {c['lname']}")
    print(f"{len(sel)} cells, {total / 1e6:.1f} MB zipped", file=sys.stderr)
    if args.list:
        return 0

    manifest = {"catalog": CATALOG_URL, "bbox": list(bbox) if bbox else None, "cells": {},
                "failed": {}}
    for n, c in enumerate(sel, 1):
        zpath = CACHE / "zips" / f"{c['name']}_{c['edtn']}_{c['updn']}.zip"
        if not zpath.exists():
            try:
                fetch(c["zipfile_location"], zpath)
            except OSError as e:
                manifest["failed"][c["name"]] = str(e)
                print(f"FAILED {c['name']}: {e}", file=sys.stderr)
                continue
        if n % 250 == 0:
            print(f"{n}/{len(sel)} cells", file=sys.stderr, flush=True)
        files = safe_extract(zpath, c["name"], out)
        manifest["cells"][c["name"]] = {"edtn": c["edtn"], "updn": c["updn"],
                                        "isdt": c["isdt"], "files": files}
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
