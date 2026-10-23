"""Thin layer over the GDAL S-57 driver: configuration, input discovery, opening cells."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from osgeo import gdal, ogr

log = logging.getLogger(__name__)

# Option names verified against the S57 driver documentation of GDAL 3.13.
S57_OPTIONS = (
    "RETURN_PRIMITIVES=OFF,RETURN_LINKAGES=OFF,LNAM_REFS=ON,"
    "UPDATES=APPLY,RECODE_BY_DSSI=ON"
)


def configure() -> None:
    gdal.UseExceptions()
    ogr.UseExceptions()
    gdal.SetConfigOption("OGR_S57_OPTIONS", S57_OPTIONS)


def discover(inputs: list[str]) -> list[Path]:
    """Return all base cell files (``*.000``) given files and/or directories, sorted."""
    found: set[Path] = set()
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".000"):
                        found.add(Path(root) / f)
        elif p.is_file() and p.name.lower().endswith(".000"):
            found.add(p)
        else:
            log.warning("ignoring input %s (not a directory or *.000 file)", item)
    return sorted(found, key=lambda q: (q.name, str(q)))


def open_cell(path: Path) -> ogr.DataSource:
    configure()
    ds = ogr.Open(str(path))
    if ds is None:
        raise RuntimeError(f"cannot open {path}")
    return ds


configure()
