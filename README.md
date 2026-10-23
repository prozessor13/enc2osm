# enc2osm

Merge any number of IHO S-57 ENC cells into **one deduplicated OSM file** (`.osm.pbf` or `.osm`)
with OpenSeaMap `seamark:*` tagging, so that ENC data can be rendered by an OSM-based seamark
pipeline such as [openwatersio/seamap](https://github.com/openwatersio/seamap).

- "Best scale wins" coverage resolution from `M_COVR` (like an ECDIS), with a seam tolerance for
  points so marks are neither lost nor duplicated at cell boundaries.
- Master/slave aggregation: a buoy and its light, topmark, fog signal and racon become one node.
- Lines and areas cut at coverage seams are re-joined.
- Mapping tables are data (`enc2osm/mapping/*.yaml`), derived from GDAL's S-57 tables and the OSM
  wiki; unknown codes are never guessed (they are dropped and counted).
- Deterministic: the same input cells give a byte-identical PBF, whatever `--workers` is.

Runtime dependencies: GDAL Python bindings + pyosmium. First tested data source: NOAA (public domain).
See `docs/REPORT.md` for results, `docs/DECISIONS.md` for the design decisions.

## Install

### Docker (recommended, pinned GDAL 3.13.3, amd64 + arm64)

```sh
docker build -t enc2osm .
docker run --rm -v "$PWD":/work -w /work enc2osm build -o out.osm.pbf ENC_ROOT/
```

### pip

GDAL's Python bindings must match the system libgdal, so install them from your platform first
(conda-forge `gdal`, Homebrew `gdal` + `pip install gdal==$(gdal-config --version)`, or the
`ghcr.io/osgeo/gdal` images), then:

```sh
pip install .            # installs `osmium` (pyosmium) and the `enc2osm` command
enc2osm --version
```

Python ≥ 3.11.

## Usage

```sh
# Convert: points only (v1) or points + areas/lines (v2)
enc2osm build -o out.osm.pbf ENC_ROOT/                       # v1 classes
enc2osm build -o out.osm.pbf --classes v2 --workers 4 ENC_ROOT/ \
       --report report/                                      # + dedup/audit/stats reports
enc2osm build -o sf.osm.pbf --bbox -122.55,37.75,-122.35,37.9 ENC_ROOT/

# Inspect inputs
enc2osm inventory ENC_ROOT/            # cell, band, edition, update, scale, units, bbox
enc2osm inventory --json ENC_ROOT/
enc2osm lnam-check ENC_ROOT/           # how often LNAMs repeat across cells (informational)
```

Inputs are `*.000` files or directories (searched recursively); update files `.001`, `.002`, …
next to a base cell are applied. If the same cell is given twice, the highest edition/update wins.

| Option | Default | Meaning |
|---|---|---|
| `--classes v1\|v2\|all` | `v1` | v1: buoys, beacons, lights, landmarks, hazards; v2: + anchorages, restricted areas, cables, pipelines, TSS, fairways, bridges, platforms |
| `--seam-tolerance M` | 50 | metres; points within this distance of a coverage seam are kept and deduplicated |
| `--bbox minx,miny,maxx,maxy` | – | read only intersecting cells, clip the output |
| `--keep-raw` | off | keep unmapped S-57 attributes as `enc:<ACRONYM>` |
| `--report DIR` | – | `dedup.csv`, `dropped_without_counterpart.csv`, `stats.json`, `stats_per_cell.json` |
| `--workers N` | 1 | parallel cells in pass 2 (output does not depend on it) |
| `--negative-ids` | off | write IDs −1, −2, …; the default 1, 2, … is required by Planetiler |

Every object carries provenance tags: `enc:cell`, `enc:band`, `enc:lnam`, `enc:scamin`,
`enc:sordat` (re-joined lines/areas list all source cells, `;`-separated).

## Rendering with SeaMap

```sh
scripts/preview.sh                               # builds the San Francisco test region
SEAMAP_DIR=~/src/seamap scripts/preview.sh       # … and renders it with bin/run (Planetiler)
```

## Development

```sh
docker build -t enc2osm:dev .
scripts/dev.sh pytest -q                         # all tests inside the pinned image
scripts/dev.sh ruff check .
scripts/dev.sh python3 scripts/fetch_fixtures.py medium     # Puget Sound, 90 cells (not committed)
scripts/dev.sh python3 -m enc2osm build -o out/m.osm.pbf --classes v2 --report out/rm fixtures/medium
scripts/dev.sh python3 scripts/check_acceptance.py out/m.osm.pbf out/rm fixtures/medium
```

Test data: `tests/data/small` (San Francisco, 14 NOAA cells) and `tests/data/golden_extra`
(one cell with cardinal/isolated-danger buoys) are committed; NOAA ENC data is public domain.

## License

MIT. Mapping tables were built independently from GDAL's S-57 tables and the OSM wiki.
