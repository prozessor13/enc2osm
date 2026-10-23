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

## D7 — Resolver details (2026-10-23)
- Issue date compares `DSID_ISDT` (YYYYMMDD, the issue date of the latest applied update).
- Sliver threshold default 10 m² per polygon part (area converted at the part's mid latitude).
  Rescheme cells share exact grid edges, so on the fixtures no slivers occur at all.
- Mask grid 0.5°. Mask parts are the *full* coverages (not the effective areas), as specified.

## D8 — Mapping tables without PyYAML (2026-10-23)
Runtime deps are GDAL + pyosmium only, so `enc2osm/yamlmini.py` parses the YAML subset the tables
use (block maps, flow lists/maps, comments, quoted scalars) and rejects everything else. A test
cross-checks it against PyYAML (dev-only dependency in the image) on all three tables.

## D9 — Units (2026-10-23)
`DSPM_DUNI`: 1 = metres, 3 = feet (×0.3048), 4 = fathoms and fractions (×1.8288);
2 = "fathoms and feet" is **not** converted (encoding of the value is unclear) — the attribute is
dropped and counted (`unit_unknown`). `DSPM_HUNI`: 1 = metres, 2 = feet. Converted values are
rounded to 0.01 m; metre values pass through unchanged. All fixture cells use metres.
Kinds `depth`/`height` are declared per attribute in `attributes.yaml`.

## D10 — MARSYS inheritance only for buoys and beacons (2026-10-23)
`system: true` in `objects.yaml` (BOY*, BCN*), matching the wiki ("Buoys, Beacons & Notices").
Inheritance from `M_NSYS` only for point objects without own `MARSYS`; if the point lies in
several `M_NSYS` areas with different values, it stays unset (counted as `marsys_conflict`).

## D11 — Aggregation rules (2026-10-23)
- Links: `LNAM_REFS` with `FFPT_RIND=2` on the master and `FFPT_RIND=1` on the slave are both
  honoured. A slave claimed by two masters stays with the first (sorted by class, LNAM), counted.
- Position fallback attaches an unreferenced slave only if **exactly one** point master sits at the
  identical position (1e-7°). Two structures at the same spot → no guess, slave stays standalone.
- Slaves of a non-point master (e.g. a lit landmark polygon) cannot share a single position with
  it → standalone at their own position (counted `slave_of_nonpoint_master`).
- Slaves whose master class is out of scope (e.g. BUISGL, BRIDGE in v1) are not resolved → standalone.
- Standalone slaves at the same position form **one** object (a multi-sector light is encoded as
  several LIGHTS at one point; one node per sector would break the style's sector rendering).
  Its type comes from the first class in LIGHTS > FOGSIG > RTPBCN > DAYMAR > TOPMAR.
- Light order on a structure: unsectored lights first, then SECTR1 ascending, then colour codes,
  then LNAM (determinism). Numbering itself happens in the tag mapping.

## D12 — Tag mapping rules (2026-10-23)
- **Lighthouses (known trap 1):** the master keeps its own type (`LNDMRK` → `landmark`,
  `BCN*` → `beacon_*`), the light goes on top as `seamark:light:*`. The reference pipeline handles
  exactly this: `Seamark.java` builds the light label for any type carrying light tags,
  `SeamarkZoomRules` promotes "a lit landmark … is an aid in its own right", and `labels.ts`
  stacks name + characteristic for lit landmarks. Major vs. minor rendering comes from
  `light_range` (≥ 10 M), not from the type. Retyping a landmark to `light_major` would lose the
  structure (tower/category/function) and is not what S-57 encodes.
- **Standalone lights:** `light_major` if max VALNMR ≥ 10 M, else `light_minor` (rules.yaml).
- **Light character (known trap 3):** `LITCHR` → `seamark:light:character` (wiki abbreviations
  F, Fl, LFl, Q, VQ, UQ, Iso, Oc, IQ, IVQ, IUQ, Mo, FFl, FlLFl, OcFl, FLFl, Al.Oc, Al.LFl, Al.Fl,
  Al.Gr, Q+LFl, VQ+LFl, UQ+LFl, Al, Al.FFl); `SIGGRP` "(3)" → `group=3`, "(2+1)" → `2+1`,
  "(A)" → `A` (Morse), "()" → no group, multi-group values like "(6)(1)" → unmapped (counted).
  `SIGPER` → `period`, `HEIGHT` → `height` (m), `VALNMR` → `range` (M). The reference style
  composes `Fl(3)W.30s47m19M` from exactly these keys (`Seamark.lightAbbr`).
- `seamark:light:N:*` numbering when there is more than one light **or** any light has sector
  limits (the style draws sector arcs only from numbered keys). One unsectored light → unnumbered.
- Other slave classes: several identical copies (e.g. one daymark per face) → emitted once;
  differing copies → numbered `seamark:daymark:N:*`.
- Name: master `OBJNAM`, else the first slave's (`seamark:name`); other slave names are dropped
  (counted `slave_name_dropped`).
- Enumerations: a list with **any** unknown code is dropped entirely (never a partial list).
- A key set twice with different values on one object (e.g. VALNMR and VALMXR both → range) is
  dropped and counted (`conflict:*`).
- `MARSYS` is emitted as `seamark:<type>:system` only for BOY*/BCN*; elsewhere ignored.
- Provenance tags: `enc:cell`, `enc:band`, `enc:lnam` (master's), `enc:scamin`, `enc:sordat`.
