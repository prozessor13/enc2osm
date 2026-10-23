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

## D13 — Seam dedup algorithm (2026-10-23)
The spec's "require a unique match" is implemented as a greedy, distance-ordered 1:1 matching:
- Candidate pairs: different cells, ≤ tolerance, same `seamark:type`, same non-empty name or (both
  unnamed) identical `colour` and `shape`; at least one point is a seam candidate.
- A pair is **ambiguous** only if one of its points has another open candidate *from the
  partner's cell* within distance + margin (margin = 20 % of the tolerance = 10 m). A cell
  encodes a physical mark once, so two such candidates means the twin cannot be identified;
  candidates from a third cell are not a contradiction (three overlapping bands).
- Merged points are removed; the kept (higher-priority) point may still absorb twins from other
  cells, but never a second one from the same cell.
- **Pairs from cells whose coverages do not overlap** (they only touch, e.g. neighbouring band-5
  grid cells) are only merged at ≤ 1 m: such cells chart a mark from the same compilation, so a
  real twin sits at the same position, while a 40 m pair there is two marks. Found on the small
  fixture: without this rule two different unnamed rocks 40 m apart in US5OAKFF/US5OAKEF were
  merged and five ambiguous pairs appeared (9.4 % of seam candidates); with it: 0 ambiguous, all
  merges at 0.0 m.
- Why not the literal rule: with real ENCs a lower band usually charts *both* of two nearby marks,
  so a higher-band mark near the seam has two lower-band candidates (its twin + the neighbour) and
  the literal rule would call it ambiguous and keep the duplicate.
- Known limitation: two different unnamed marks with identical colour/shape, ≤ tolerance apart
  across a seam of *overlapping* cells, where each is charted by only one of the cells, are
  indistinguishable from one mark with a position offset and get merged.

## D14 — Dropped-object audit interpretation (2026-10-23)
Counterpart = an output point with the same `seamark:type` within 2× tolerance, **or** with the
same type and the same non-empty name within 1000 m (equirectangular). Classification helper:
`scripts/classify_dropped.py` (position / type / edition / not_charted).

## D15 — Lines/areas in v1 classes (2026-10-23)
LNDMRK, MORFAC, WRECKS, OBSTRN also occur as lines/areas. They go through the line/area path
(clip without buffer, re-join) already in `--classes v1`; only points get the seam buffer.
Closed linear ways get `area=no` (Planetiler treats closed ways as polygons unless `area=no`,
see OsmReader.canBePolygon in planetiler-core 0.10.2, the version the reference pipeline uses).

## D16 — Object IDs: positive and ascending by default (2026-10-23) — deviates from CLAUDE.md
CLAUDE.md asks for negative IDs. The reference consumer cannot read them: Planetiler 0.10.2 (the
version openwatersio/seamap pins) stores node locations in `SparseArrayLongLongMap` /
`SortedTableLongLongMap`, whose `put()` throws "Nodes must be sorted ascending by ID" unless every
key is > the previous one, starting from -1 — so -1, -2, … fails on the second node, and pyosmium's
default location index ignores negative IDs as well. Default is therefore 1, 2, 3, … per object
type, assigned in the same deterministic order (seamark nodes sorted by cell, class, LNAM; then
way vertices in way order). `--negative-ids` writes -1, -2, … exactly as specified, for consumers
that need IDs that cannot collide with real OSM data. The file is never merged with OSM data or
uploaded (CLAUDE.md), so positive IDs carry no collision risk in the intended pipeline.
**Needs confirmation by the user.**

## D17 — Criterion 4 check counts cross-cell pairs only (2026-10-23)
The first version of the check flagged 6 pairs on the medium fixture; all 6 are two *different*
S-57 objects of the *same* cell that share a name (e.g. two "Edmonds Fishing Reef Buoy" 40 m apart
in US5SEAIL, two "Bangor South Floating Security Barrier Light" 86 m apart in US5SEAHG). They are
not seam duplicates and removing one would lose a mark. The check now evaluates pairs from
different cells (what seam dedup is responsible for) and lists same-cell pairs separately in
`acceptance.json` / REPORT.md.

## D18 — v2 classes (2026-10-23)
Mapped: ACHARE, ACHBRT, RESARE, CBLSUB, CBLARE, CBLOHD, PIPSOL, PIPARE, OFSPLF, TSSLPT, TSSBND,
TSELNE, TSEZNE, FAIRWY, BRIDGE with CATACH, RESTRN, CATREA, CATCBL, CATPIP, PRODCT, CATOFP, CATBRG,
CATTSS, TRAFIC, VERCLR/VERCCL/VERCOP/VERCSA (height units), DRVAL1/DRVAL2 (depth units).
OFSPLF and BRIDGE are masters (lights/daymarks on platforms and bridges attach to them when they are
points). Not mapped: DWRTPT (no wiki type), HORCLR/RADIUS/BURDEP (unit unclear), supplement codes
(OPEN_QUESTIONS Q1). Areas are written as closed ways or multipolygon relations, lines as ways
(`area=no` when closed). 17 hand-derived v2 golden cases.
