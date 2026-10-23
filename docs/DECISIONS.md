# Decisions

Each entry: decision, reasoning, date. Ambiguities are resolved conservatively.

## D1 — Base image and toolchain (2026-10-23)
`ghcr.io/osgeo/gdal:ubuntu-small-3.13.3`, pinned by digest
(`sha256:64250faf…0b40`, multi-arch, arm64 verified on the dev Mac). GDAL 3.13.3, Python 3.14.
pyosmium comes from Ubuntu (`python3-pyosmium=4.3.0-1build1`) so it links the distro
libosmium; `osmium-tool=1.19.0-1build1` and pytest/ruff are dev tools only.
`pip install --no-deps` in the image because the GDAL bindings are built into the base image and
have no pip metadata; `pyproject.toml` therefore only declares `osmium`.

## D2 — Fixture catalog (2026-10-23)
NOAA publishes two catalogs. `ENCProdCat.xml` (10 MB) is used: it has `status`, `edtn`, `updn`,
`cscale`, `zipfile_location` and coverage panels per cell. The ISO 19115 variant (52 MB) carries the
same polygons but no status. Cells with `status=Cancelled` (193 of 7307) carry no coverage and are
skipped. Selection = any catalog panel intersects the bbox (OGR), all bands.

Note: NOAA today ships ~7100 active cells (post-rescheme grid), not ~1000 — relevant for the
full-set estimate.

## D3 — Fixture regions (2026-10-23)
- small: San Francisco, bbox `-122.53,37.78,-122.36,37.85` → 14 cells, bands 1–5, 12 MB unpacked,
  committed under `tests/data/small/` (< 20 MB).
- medium: Puget Sound, bbox `-122.75,47.25,-122.25,48.00` → 90 cells (1×b1, 1×b2, 4×b3, 12×b4,
  72×b5), cached under `fixtures/medium/` (not committed).
No band-6 cells in either region (NOAA has only 64 band-6 cells). Same-band overlap: see Phase 2.

## D4 — No same-band overlap in NOAA data (2026-10-23)
Checked all 7114 active NOAA cells pairwise per band (catalog panels, OGR intersection): **zero**
same-band overlaps with positive area. The resolver still handles them (tie-breakers scale →
issue date → name); the case is covered by synthetic tests only.

## D5 — Coverage = union(CATCOV=1) − union(CATCOV=2) (2026-10-23)
CLAUDE.md asks for the union of `CATCOV=1`. `CATCOV=2` ("no coverage") polygons are additionally
subtracted: if a producer encodes a data hole inside a covered polygon, claiming it would make this
cell win an area where it has no data and drop lower-band objects there (loss). Subtracting can
only shrink a cell's claim, i.e. hand the area to a lower-priority cell. NOAA fixtures: no effect.
Coverage geometries are made valid (`MakeValid`) and reduced to their polygonal part.

## D6 — Duplicate cell names (2026-10-23)
Highest `DSID_EDTN`, then highest `DSID_UPDN` (after applying updates), then path (determinism).
The loser is listed as skipped with reason "duplicate".
