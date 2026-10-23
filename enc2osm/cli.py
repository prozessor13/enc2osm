"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import sys

from enc2osm import __version__


def _add_inputs(p: argparse.ArgumentParser) -> None:
    p.add_argument("inputs", nargs="+", metavar="INPUT",
                   help="S-57 base cells (*.000) or directories searched recursively")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="enc2osm", description=__doc__)
    ap.add_argument("--version", action="version", version=f"enc2osm {__version__}")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="convert cells into one deduplicated OSM file")
    p.add_argument("-o", "--output", required=True, help="output file (.osm.pbf or .osm)")
    _add_inputs(p)
    p.add_argument("--classes", choices=["v1", "v2", "all"], default="v1",
                   help="object classes: v1 points, v2 + areas/lines (default v1)")
    p.add_argument("--bbox", help="minx,miny,maxx,maxy: read only intersecting cells, clip output")
    p.add_argument("--seam-tolerance", type=float, default=50.0, metavar="M",
                   help="seam tolerance in metres (default 50)")
    p.add_argument("--keep-raw", action="store_true",
                   help="keep unmapped S-57 attributes as enc:<ACRONYM>")
    p.add_argument("--report", metavar="DIR", help="write dedup/audit/stats reports here")
    p.add_argument("--workers", type=int, default=1, help="parallel cells in pass 2 (default 1)")

    p = sub.add_parser("inventory", help="list cells with band, edition, scale, coverage")
    _add_inputs(p)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("lnam-check", help="count LNAMs shared between cells")
    _add_inputs(p)
    p.add_argument("--json", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    if args.command == "build":
        from enc2osm.build import run
        return run(args)
    if args.command == "inventory":
        from enc2osm.inventory import run
        return run(args)
    if args.command == "lnam-check":
        from enc2osm.lnamcheck import run
        return run(args)
    return 2
