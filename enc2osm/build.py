"""`enc2osm build`: inventory -> coverage -> pass 2 per cell -> finalize -> .osm.pbf + reports."""

from __future__ import annotations

import csv
import json
import logging
import multiprocessing as mp
import os
import resource
import time
from collections import Counter
from pathlib import Path

from osgeo import gdal

from enc2osm import coverage, dedup, inventory, mapping, rejoin, writer
from enc2osm.coverage import m_to_deg
from enc2osm.pass2 import CellResult, Options, PointObj, bbox_geom, process_cell

log = logging.getLogger(__name__)

DEDUP_MARGIN_FRACTION = 0.2  # of the seam tolerance, see dedup.py / DECISIONS D13


def agency_names() -> dict[int, str]:
    path = gdal.FindFile("gdal", "s57agencies.csv")
    out = {}
    if path:
        with open(path, encoding="latin-1") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split(",", 3)
                if len(parts) == 4 and parts[2].isdigit():
                    out[int(parts[2])] = parts[3].strip().strip('"')
    return out


def attribution(cells) -> str:
    names = agency_names()
    agencies = sorted({c.agency for c in cells if c.agency is not None})
    who = "; ".join(f"{names.get(a, 'agency ' + str(a))}" for a in agencies) or "unknown"
    return f"IHO S-57 ENC data from: {who}"


class CoverageOverlap:
    """Cached test: do two cells' M_COVR coverages overlap with more than a sliver?"""

    def __init__(self, cells, sliver_m2: float):
        self.cells = {c.name: c for c in cells}
        self.sliver_m2 = sliver_m2
        self.cache: dict[tuple[str, str], bool] = {}

    def __call__(self, a: str, b: str) -> bool:
        key = (a, b) if a < b else (b, a)
        if key not in self.cache:
            ca, cb = self.cells[key[0]], self.cells[key[1]]
            inter = ca.coverage.Intersection(cb.coverage)
            area = inter.GetArea() if not inter.IsEmpty() else 0.0
            lat = (ca.bbox[1] + ca.bbox[3]) / 2
            self.cache[key] = area > coverage.m2_to_deg2(self.sliver_m2, lat)
        return self.cache[key]


def _work(args) -> CellResult:
    cell, eff, scope_opts = args
    return process_cell(cell, eff, mapping.load(), scope_opts)


def run_pass2(cells, effs, opts: Options, workers: int) -> list[CellResult]:
    jobs = [(c, effs[c.name], opts) for c in sorted(cells, key=lambda c: c.name)]
    if workers <= 1:
        results = [_work(j) for j in jobs]
    else:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = list(pool.imap_unordered(_work, jobs, chunksize=1))
    return sorted(results, key=lambda r: r.cell)  # independent of worker scheduling


def peak_rss_mb() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return max(own, kids) / 1024  # Linux: KiB


def build(inputs, output, opts: Options, report_dir: str | None, workers: int = 1) -> dict:
    t0 = time.time()
    cells, skipped = inventory.build(inputs)
    if opts.bbox:
        box = bbox_geom(opts.bbox)
        outside = [c for c in cells if not c.coverage.Intersects(box)]
        cells = [c for c in cells if c.coverage.Intersects(box)]
        log.info("bbox: %d cells intersect, %d outside", len(cells), len(outside))
    if not cells:
        raise SystemExit("no usable cells")
    effs = coverage.resolve(cells, sliver_m2=opts.sliver_m2)
    t1 = time.time()
    results = run_pass2(cells, effs, opts, workers)
    t2 = time.time()

    points = [p for r in results for p in r.points]
    dropped = [p for r in results for p in r.dropped]
    shapes = [s for r in results for s in r.shapes]
    tol = opts.seam_tolerance
    kept, decisions = dedup.dedup(points, tol, DEDUP_MARGIN_FRACTION * tol,
                                  overlaps=CoverageOverlap(cells, opts.sliver_m2))
    missing = dedup.audit(dropped, kept, tol)
    max_lat = max(max(abs(c.bbox[1]), abs(c.bbox[3])) for c in cells)
    merged, rejoin_stats = rejoin.rejoin(shapes, m_to_deg(tol, max_lat))
    kept.sort(key=lambda p: (p.cell, p.cls, p.lnam, p.x, p.y))
    wstats = writer.write(output, kept, merged, attribution(cells), opts.bbox)
    t3 = time.time()

    seam = sum(p.seam for p in points)
    amb = sum(d.action == "ambiguous" for d in decisions)
    summary = {
        "cells": len(cells), "skipped_cells": [vars(s) for s in skipped],
        "points_kept_before_dedup": len(points), "points_written": len(kept),
        "seam_candidates": seam,
        "seam_merges": sum(d.action == "merged" for d in decisions),
        "ambiguous": amb, "ambiguous_share": round(amb / seam, 4) if seam else 0.0,
        "dropped_by_clipping": len(dropped), "dropped_without_counterpart": len(missing),
        "shapes_before_rejoin": len(shapes), "shapes_written": len(merged), **rejoin_stats,
        **wstats,
        "time_s": {"pass1": round(t1 - t0, 2), "pass2": round(t2 - t1, 2),
                   "finalize": round(t3 - t2, 2), "total": round(t3 - t0, 2)},
        "peak_rss_mb": round(peak_rss_mb(), 1), "workers": workers,
        "options": {"scope": opts.scope, "seam_tolerance": tol, "keep_raw": opts.keep_raw,
                    "bbox": opts.bbox},
    }
    if report_dir:
        write_reports(Path(report_dir), results, decisions, missing, effs, cells, summary)
    return summary


def write_reports(d: Path, results, decisions, missing, effs, cells, summary) -> None:
    d.mkdir(parents=True, exist_ok=True)
    dedup.write_decisions(d / "dedup.csv", decisions)
    by_name = {c.name: c for c in cells}
    with open(d / "dropped_without_counterpart.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "band", "issue_date", "lnam", "class", "seamark_type", "name", "lon",
                    "lat", "covering_cell", "covering_band", "covering_issue_date"])
        for p, _ in missing:
            cov = covering_cell(p, effs, by_name)
            c = by_name[p.cell]
            w.writerow([p.cell, c.band, c.issue_date, p.lnam, p.cls,
                        p.tags.get("seamark:type"), p.tags.get("seamark:name", ""),
                        f"{p.x:.7f}", f"{p.y:.7f}", cov.name if cov else "",
                        cov.band if cov else "", cov.issue_date if cov else ""])
    total = Counter()
    per_cell = {}
    for r in results:
        total.update(r.stats)
        per_cell[r.cell] = dict(sorted(r.stats.items()))
    summary_out = dict(summary)
    summary_out["global_stats"] = dict(sorted(total.items()))
    (d / "stats.json").write_text(json.dumps(summary_out, indent=1, sort_keys=True) + "\n")
    (d / "stats_per_cell.json").write_text(json.dumps(per_cell, indent=1, sort_keys=True) + "\n")


def covering_cell(p: PointObj, effs, by_name):
    from osgeo import ogr
    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint_2D(p.x, p.y)
    for name, e in sorted(effs.items(), key=lambda kv: kv[1].rank):
        if name != p.cell and e.geom.Intersects(pt):
            return by_name[name]
    return None


def run(args) -> int:
    bbox = tuple(float(v) for v in args.bbox.split(",")) if args.bbox else None
    if bbox and len(bbox) != 4:
        raise SystemExit("--bbox needs minx,miny,maxx,maxy")
    opts = Options(scope=args.classes, seam_tolerance=args.seam_tolerance,
                   keep_raw=args.keep_raw, bbox=bbox)
    workers = max(1, min(args.workers, os.cpu_count() or 1))
    summary = build(args.inputs, args.output, opts, args.report, workers)
    print(json.dumps({k: v for k, v in summary.items() if k != "skipped_cells"}, indent=1))
    return 0
