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

    p = sub.add_parser("lnam-check", help="count LNAMs shared between cells")
    _add_inputs(p)
    p.add_argument("--json", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    if args.command == "lnam-check":
        from enc2osm.lnamcheck import run
        return run(args)
    return 2
