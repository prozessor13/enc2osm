# enc2osm — S-57 ENC → OSM converter

## Goal

**End goal (context):** one MapLibre style that renders vector tiles built from OSM data (SeaMap / Open Waters Seamap) **and** tiles built from official S-57 ENCs. Instead of writing a second style, ENC data is converted into the same OSM `seamark:*` schema and fed through the same OSM-based tile pipeline.

**This project:** a CLI tool that merges any number of IHO S-57 ENC cells into **one deduplicated OSM file** (`.osm.pbf`) using OpenSeaMap `seamark:*` tagging. First data source is NOAA (public domain); the code must not assume NOAA-specific cell naming or attributes, because other producers (e.g. EU) may follow.

**Reference consumer:** https://github.com/openwatersio/seamap (tile pipeline + style; a fork of prozessor13/seamap). "Correct output" means: the tags this pipeline/style reads, with the meaning the OSM wiki defines for them.

The output PBF is rendered **on its own** as a separate tile source. Merging with OSM planet data is out of scope. Nothing is ever uploaded to openstreetmap.org.

### What matters most (in this order)

1. **No wrong seamarks** (wrong type, colour, shape, light character). A wrong buoy is worse than a missing attribute.
2. **No lost seamarks** at cell seams.
3. **No duplicate seamarks** where cells overlap.
4. Attribute completeness for what the reference style reads.
5. Performance.

## Hard constraints

- Language: Python ≥ 3.11.
- Runtime dependencies: **GDAL Python bindings (`osgeo.ogr/osr`) + `osmium` (pyosmium) only.** No shapely, no PostGIS, no database server. All geometry ops via OGR/GEOS (`Union`, `Difference`, `Intersection`, `Buffer`, `Intersects`). Stdlib `sqlite3` is allowed as a temp store only.
- Design for scale (the full NOAA set, ~1000+ cells, must be feasible later): process cell by cell; never load all features of all cells into memory at once (exception: seamark points, see Phase 6). **This run only builds test regions** — no full NOAA build.
- Deterministic output: same input cells → byte-identical PBF (stable ID assignment, sorted iteration, no dependence on worker scheduling).
- Distribution: pip-installable package with console entry point `enc2osm`, plus a Dockerfile based on a pinned `ghcr.io/osgeo/gdal` image (this is the "binary").

## Working mode: autonomous

Work through **all phases without asking for input**. Present only the finished result (see "Final deliverable"). The user will not answer questions mid-run.

- Track progress in `docs/PROGRESS.md` (phase, status, what was verified). Re-read it after any context loss.
- One commit series per phase on branch `main`. Do not start a phase before the previous one passes its tests. Remote: `origin` = https://github.com/prozessor13/enc2osm (private project of the user). Push to `origin` only when the user asks.
- Decide, don't ask: when something is ambiguous, pick the most conservative option, implement it, and record the decision with its reasoning in `docs/DECISIONS.md`.
- Don't guess S-57 semantics. If an enumeration value or tag mapping is unclear, leave it unmapped, count it in the stats report, and add it to `docs/OPEN_QUESTIONS.md`. An unmapped value is acceptable; a wrong one is not.
- Never weaken a test or acceptance check to make it pass. If a check turns out to be wrong, fix the check and document why in `docs/DECISIONS.md`.
- Minimal diffs within a phase. No refactoring or reformatting outside the current task.
- Mapping tables are data, not code: keep them in `enc2osm/mapping/*.yaml`. Every mapping change needs a golden test.
- Dev machine is a **MacBook Air (Apple Silicon)**. Run everything (tests, builds, fixture downloads) inside the project's Docker image so the GDAL version is the pinned one; verify the pinned `ghcr.io/osgeo/gdal` tag has an arm64 variant. If Docker is unavailable or the image has no arm64 build, fall back to a native GDAL (conda-forge or Homebrew), pin the version, and record it in `docs/DECISIONS.md`.
- Keep runs laptop-friendly: no job should need more than ~4 GB RAM; use `--workers` ≤ 4.

### Stop conditions

Stop and write the final report early (status: blocked) only if:

- NOAA ENC downloads are impossible from this environment (no network), or
- a hard constraint (dependencies, no database) is provably unachievable — explain why with evidence.

Everything else is solved or documented, not escalated.

## Background: the problems this tool solves

1. **Relational vs. flat.** S-57 is relational: a buoy (master) and its light, topmark, fog signal (slaves) are separate objects linked via LNAM references. OSM seamark tagging flattens them onto **one node** with `seamark:light:*`, `seamark:topmark:*`, etc.
2. **Overlapping cells.** ENC cells of different usage bands (1 overview … 6 berthing) overlap, and legacy cells may also overlap within the same band. The same physical buoy appears in several cells, often with slightly different positions and attributes. LNAM is **not** confirmed to be shared across cells for the same real-world object → no LNAM-based cross-cell dedup. Instead: coverage clipping ("best scale wins"), like an ECDIS does.
3. **Coverage ≠ bounding box.** Coverage is given by `M_COVR` polygons with `CATCOV=1`, not by the cell's bounding box.
4. **Seams lose or duplicate objects.** Because positions differ between bands, a hard clip at a coverage boundary can keep **both** versions of a buoy (duplicate) or drop **both** (loss). Therefore points are clipped with a tolerance buffer and then deduplicated (Phase 6).
5. **Seams split lines and areas.** Clipping cuts areas (anchorages, restricted areas) and lines (cables, TSS) into pieces per cell. Pieces with identical tags must be re-joined, otherwise the style draws artificial borders and duplicate labels (Phase 6).
6. **Asynchronous editions.** A newer lower-band cell can contain an object (e.g. a newly laid buoy) that an older higher-band cell covering the same area does not have yet. "Best scale wins" drops it. This cannot be fully solved; it must be **measured and reported** (acceptance criterion 8).

## Architecture: two passes

```
Pass 1 (cheap):  all cells → DSID + M_COVR → inventory → coverage resolver → effective area per cell
Pass 2 (heavy):  per cell → read features → normalize units → aggregate master/slave
                 → map to tags → clip against effective area (+ tolerance buffer)
                 → points: in-memory seam pool / lines+areas: temp store
Finalize:        point dedup + line/area re-join → OSM writer (nodes, ways, relations) → .osm.pbf
```

Note the order in Pass 2: **aggregate before clipping**, so a light is never separated from its buoy at a seam.

## Units and distances

- All geometry stays in WGS84 lon/lat.
- Tolerances are given in meters. Convert per cell: `deg = m / (111_320 · cos φ)`, with φ = the cell's maximum absolute latitude (this over-buffers in latitude, which is the conservative direction: more seam candidates, never fewer).
- Point-to-point distances for dedup: equirectangular approximation (fine for ≤ 1 km).
- Out of scope, document as known limitation: cells crossing the antimeridian (Aleutians, Guam/CNMI region).

## GDAL read settings

```python
gdal.SetConfigOption("OGR_S57_OPTIONS",
    "RETURN_PRIMITIVES=OFF,RETURN_LINKAGES=OFF,LNAM_REFS=ON,"
    "UPDATES=APPLY,RECODE_BY_DSSI=ON")
```

`UPDATES=APPLY` applies `.001`, `.002`, … found next to the `.000`. Input discovery: accept files and directories; recurse for `*.000`.

Verify all option names against the GDAL S57 driver docs of the pinned GDAL version.

## Phases

### Phase 0 — Scaffold + LNAM experiment

- Package layout, CLI skeleton (`argparse` — no extra deps), Dockerfile, pytest, ruff.
- Test fixtures: `scripts/fetch_fixtures.py` selects cells **by bounding box** from NOAA's ENC product catalog (find the catalog and download URL pattern on nauticalcharts.noaa.gov / charts.noaa.gov; verify before hardcoding). Fixture regions:
  - **Small** (unit/golden tests, committed to the repo if < 20 MB, otherwise cached): one harbour area including all cells of every band that cover it, e.g. a part of San Francisco Bay.
  - **Medium** (integration): a region with many overlapping cells of all bands, including same-band overlap, e.g. Puget Sound or Chesapeake Bay.
  If the suggested regions don't contain the needed overlap cases, pick others and record the choice in `docs/DECISIONS.md`.
- Command `enc2osm lnam-check INPUT…`: reports for BOYLAT/BOYCAR/BOYSAW/BOYSPP/BOYISD/BCN*/LIGHTS how many LNAMs occur in more than one cell. Result goes into `docs/REPORT.md`. Informational only; no design depends on it.

### Phase 1 — Inventory

For each cell, read the `DSID` layer: cell name, `DSID_INTU` (usage band 1–6), `DSID_EDTN`, `DSID_UPDN`, `DSID_ISDT`, `DSPM_CSCL` (compilation scale), `DSPM_DUNI` (depth units), `DSPM_HUNI` (height units). Read `M_COVR` polygons where `CATCOV=1` and union them per cell.

Edge cases:

- Same cell name given more than once (e.g. two download dates): keep the highest edition, then highest update number; warn.
- Cell without usable `M_COVR`: skip it, log it in the report (conservative: no guessing of coverage).
- Cell that fails to open: skip, log, continue.

Output: list of `CellInfo` dataclasses. Command `enc2osm inventory INPUT…` prints it as a table / JSON.

### Phase 2 — Coverage resolver

Order cells by priority, highest first:

1. usage band descending,
2. larger compilation scale (smaller `CSCL` value),
3. newer issue date,
4. cell name (for determinism).

Iterate in that order with an accumulated mask:

```
effective[cell] = coverage[cell] − mask
mask = mask ∪ coverage[cell]
```

This handles both cross-band overlap (harbour cuts out approach) and same-band overlap (tie-breaker).

Performance: keep `mask` as a list of polygons plus a simple grid index instead of one giant union. Only difference against the mask parts intersecting the cell's envelope. Drop slivers below a configurable area threshold from effective areas.

Tests: synthetic polygons (nested, partially overlapping, same-band overlap), plus the fixture cells.

### Phase 3 — Feature extraction

Per cell, for the object classes in scope (see Phase 5):

- Read features, attach provenance: `enc:cell`, `enc:band`, `enc:lnam`, `enc:scamin` (if present), `enc:sordat` (if present).
- Normalize units to meters: depth attributes such as `VALSOU` (WRECKS/OBSTRN/UWTROC) per `DUNI`; heights such as `HEIGHT`/`VERCLR` per `HUNI` (feet 0.3048, fathoms 1.8288). `VALNMR` stays in nautical miles.
- Read `M_NSYS` polygons of the cell: objects without their own `MARSYS` inherit it from the `M_NSYS` area containing them.

### Phase 4 — Master/slave aggregation (within one cell, before clipping)

- Use `LNAM_REFS` + `FFPT_RIND` on master objects to collect slaves (LIGHTS, TOPMAR, FOGSIG, RTPBCN, DAYMAR, RDOSTA, …).
- Fallback: slaves without a master → group with the structure object at identical coordinates in the same cell.
- Slaves without any structure (e.g. a standalone LIGHTS) become their own node; their `seamark:type` follows a rule defined in the mapping YAML (e.g. `light_major` / `light_minor`), derived from the OSM wiki and the reference style, documented in `docs/DECISIONS.md`.
- Multiple lights on one structure → `seamark:light:1:*`, `seamark:light:2:*`, … numbered by `SECTR1` ascending, then by colour, for determinism. A single light without sectors uses the unnumbered `seamark:light:*`.
- The aggregated object has exactly one position: the master's.

### Phase 5 — Tag mapping

Tables in `enc2osm/mapping/`:

- `objects.yaml`: S-57 acronym → `seamark:type` value, allowed geometry, scope (v1/v2).
- `attributes.yaml`: S-57 attribute acronym → OSM attribute key (e.g. `COLOUR → colour`, `BOYSHP → shape`, `CATLAM → category`, `LITCHR → character`, `SIGPER → period`, `VALNMR → range`, `SECTR1/SECTR2 → sector_start/sector_end`, `OBJNAM → seamark:name`).
- `values.yaml`: enumerations (numeric code → OSM string), e.g. `COLOUR 1 → white`, `3 → red`, `4 → green`.

Sources, in this order:

1. GDAL's bundled `s57objectclasses.csv`, `s57attributes.csv`, `s57expectedinput.csv` (in `GDAL_DATA`) for the S-57 side (codes and descriptions).
2. OSM wiki pages `Seamarks/Seamark_Objects` and `Seamarks/Seamark_Attributes` for the OSM side.
3. The tags the reference style actually reads (extract them from https://github.com/openwatersio/seamap) — those have priority.

**License note:** do not copy mapping tables from GPL code (JOSM seachart, quantenschaum/mapping) verbatim; use them only to cross-check.

Tagging rules:

- List attributes → `;`-separated values.
- `seamark:type` = master object; slave attributes as `seamark:<slave>:<attr>`; shared attributes like the name as `seamark:name`.
- Buoyage system: `MARSYS` (own or inherited from `M_NSYS`) → `seamark:<type>:system` (`iala-a` / `iala-b`). If neither exists, leave unset (the style applies defaults).
- Unmapped attributes → keep as `enc:<ACRONYM>=<raw value>` only with `--keep-raw`; otherwise drop and count in the stats report.

Known traps — check against the reference style and decide explicitly in `docs/DECISIONS.md`:

- **Lighthouses:** a landmark/structure master (LNDMRK, BUISGL, …) carrying a major light. Does the style expect `seamark:type=light_major` with light tags, or the landmark type plus light tags?
- **Area vs. line:** how does the reference pipeline decide whether a closed way is an area (tag such as `area=yes`, or by `seamark:type`)? Emit accordingly.
- **Light character:** how `LITCHR` + `SIGGRP` map to `seamark:light:character` and `seamark:light:group` (e.g. `Fl(3)`) so that the style's label `Fl(3)W.30s47m19M` comes out right.

Scope v1 (seamarks and hazards — points):
BOYLAT, BOYCAR, BOYSAW, BOYSPP, BOYISD, BOYINB, BCNLAT, BCNCAR, BCNSAW, BCNSPP, BCNISD, LIGHTS, LITFLT, LITVES, TOPMAR, FOGSIG, RTPBCN, DAYMAR, LNDMRK, PILPNT, MORFAC, WRECKS, OBSTRN, UWTROC.

Scope v2 (areas and lines): ACHARE, ACHBRT, RESARE, CBLSUB, CBLARE, PIPSOL, PIPARE, OFSPLF, TSSLPT, TSSBND, TSELNE, TSEZNE, FAIRWY, DWRTPT, BRIDGE, CBLOHD (to be extended).

Not in scope: DEPARE, DEPCNT, SOUNDG and other bathymetry objects (depth comes from Seascape, not from this tool), LNDARE, COALNE (OSM coastline is used), meta objects except M_COVR and M_NSYS.

This run: **v1 must meet all acceptance criteria first.** Then implement v2; acceptance criteria apply to v2 as far as implemented, and anything left open is listed in the report.

### Phase 6 — Clipping, seam dedup and re-join

**Points (aggregated objects):**

- Keep if the position intersects `effective[cell]` **buffered by the seam tolerance** (default 50 m).
- Points within the tolerance of the effective area's boundary (inside or outside) are flagged `seam_candidate`.
- Keep all kept points of all cells in memory (NOAA seamarks are in the order of 10⁵).
- For each `seam_candidate`, find points from a **different cell** within the tolerance with the same `seamark:type` and either the same `seamark:name` or (both names empty) identical colour and shape tags.
- Require a **unique** match. Unique match → keep the version from the higher-priority cell (Phase 2 ordering), drop the other. Multiple candidates → keep all, log as ambiguous.
- Log every decision to `report/dedup.csv`.

**Lines and areas (v2):**

- Clip with `Intersection` against `effective[cell]` (no buffer). Drop empty results and slivers.
- Re-join pieces from different cells whose tags are identical (ignoring `enc:*` provenance) and which touch within the tolerance: areas by union (with snapping), lines by joining at matching endpoints. The merged feature gets `enc:cell` as a sorted `;`-list of all source cells.

**Dropped-object audit** (input for acceptance criterion 8): every point dropped because it lies in a higher-priority cell's coverage is looked up in the output (same `seamark:type` within 2× tolerance, or same name). Points without counterpart are written to `report/dropped_without_counterpart.csv`.

### Phase 7 — OSM writer

- Use pyosmium `SimpleWriter` to write `.osm.pbf` (and `.osm` XML via file extension).
- Negative IDs, assigned deterministically (sorted by cell, object class, LNAM).
- **Seamark point objects always get their own node** and are never merged with other nodes, even at identical coordinates.
- Way vertices: dedup via a dict keyed by coordinates quantized to 1e-7°, among way vertices only. If memory becomes an issue, swap to an on-disk store behind the same interface (stdlib `sqlite3`).
- Write order: all nodes, then ways, then relations. Lines/areas are spooled to temp files and written in order at finalize.
- Areas: simple polygon → closed way; polygons with holes / multipolygons → `type=multipolygon` relation. Split ways longer than 2000 nodes.
- File header: `generator=enc2osm <version>`; source attribution to NOAA in the header.

### Phase 8 — CLI, stats, packaging

```
enc2osm build   -o out.osm.pbf  INPUT… [--classes v1|v2|all] [--bbox minx,miny,maxx,maxy]
                [--seam-tolerance 50] [--keep-raw] [--report DIR] [--workers N]
enc2osm inventory INPUT…
enc2osm lnam-check INPUT…
```

- `--workers`: parallelize Pass 2 per cell (multiprocessing). Results are sorted before finalize, so output does not depend on scheduling. The finalize step stays single-threaded.
- `--bbox`: only cells intersecting the bbox are read; output is clipped to the bbox.
- Stats report: per cell — features read / kept / clipped / unmapped attributes; global — seam merges, ambiguous seams, dropped objects without counterpart, skipped cells.
- Validate output: `osmium fileinfo -e` and `osmium check-refs` (osmium-tool in the Docker image as a dev dependency only).

## Tests

- **Unit:** coverage resolver (synthetic geometries), unit normalization, light numbering, value mapping, `M_NSYS` inheritance.
- **Seam scenarios (synthetic):** same buoy in two bands, offset 20 m across the boundary in both directions (must end up exactly once, never zero times); two different unnamed buoys 30 m apart across the boundary (must both survive); an area split by a coverage boundary (must be re-joined).
- **Golden:** for ~30 hand-picked objects from the small fixture (lateral/cardinal/special buoys, beacons, sector lights, multi-light structures, a lighthouse, wrecks, rocks), write the expected tags **derived by hand from the raw S-57 attributes and the OSM wiki definitions** — not by running the code. Each golden entry cites the raw attribute values it was derived from.
- **Plausibility against OSM** (metric, not pass/fail): download the existing OSM seamarks for the medium region (Geofabrik extract or Overpass) and match them to the output by type and distance < 100 m. Report the agreement rate for `seamark:type`, colour, shape, and light character. Investigate every systematic disagreement (> 5 % for one attribute) and either fix it or document it.

## Acceptance criteria (all must hold before presenting)

1. All unit, seam-scenario and golden tests are green inside the Docker image.
2. Medium fixture: `osmium fileinfo -e` and `osmium check-refs` are clean.
3. Coverage invariants, checked by an automated script on the medium fixture:
   - every output point lies inside the buffered effective area of its `enc:cell`; every line/area lies inside the union of the effective areas of its `enc:cell` list;
   - the union of all effective areas equals the union of all `M_COVR` coverages (within tolerance);
   - effective areas don't overlap each other.
4. Dedup invariant: no two seamark nodes with the same `seamark:type` and the same non-empty `seamark:name` within 2× seam tolerance, except pairs logged as ambiguous. Ambiguous pairs must be < 1 % of seam candidates and are listed individually in `REPORT.md`.
5. No orphaned slaves: every LIGHTS/TOPMAR/FOGSIG either sits on a structure node or is intentionally standalone (counted in the report).
6. Determinism: two builds of the medium fixture (one with `--workers 1`, one with `--workers 4`) produce byte-identical PBFs.
7. Medium fixture: report wall time, peak RSS and number of cells/features. Target: peak RSS < 4 GB. From these numbers, estimate time and memory for the full NOAA set and name the expected bottleneck (no full build in this run).
8. Dropped-object audit: number of dropped objects without counterpart is reported; at least 10 of them (or all, if fewer) are examined and classified (edition difference / position difference beyond tolerance / bug). Every bug found is fixed.
9. Every `seamark:type` value and every enumeration value in the output exists in the mapping tables (no free-text leakage).
10. Tags read by the reference style are covered: report which ones the output produces and which it doesn't, with reasons. The three known traps (Phase 5) are decided and documented.

## Final deliverable

When all acceptance criteria hold (or a stop condition is reached), present:

- `docs/REPORT.md`: what was built, how to run it, results of every acceptance criterion with numbers, the OSM plausibility metrics, performance figures, the LNAM-check result, known limitations.
- `docs/DECISIONS.md` and `docs/OPEN_QUESTIONS.md`, complete.
- `README.md` with install (pip and Docker) and usage examples.
- Git tag `v0.1.0` on `main`.

A visual check against the NOAA chart viewer and a render through the SeaMap tile pipeline will be done by the user afterwards; prepare `scripts/preview.sh` that builds the small fixture so this is a one-liner.

## Decisions (fixed for this run)

| # | Decision | Value |
|---|---|---|
| 1 | Language | Python |
| 2 | Tool license | MIT (mapping tables built independently, see license note) |
| 3 | Depth data (DEPARE/DEPCNT/SOUNDG) | Not converted; Seascape stays the depth source |
| 4 | Provenance tags | `enc:cell`, `enc:band`, `enc:lnam`, `enc:scamin`, `enc:sordat` on every object |
| 5 | Merging with existing OSM seamarks | Out of scope; the ENC PBF is rendered as its own tile source |
| 6 | Seam tolerance | 50 m (configurable) |
