# enc2osm — Report (v0.1.0, 2026-10-23)

Sections 1–9 describe v0.1.0 (test regions). Section 10 adds the first full NOAA build and the
fixes it led to (after the tag, on `main`).

## 1. What was built

`enc2osm` merges IHO S-57 ENC cells into one deduplicated OSM file with OpenSeaMap `seamark:*`
tagging, for rendering with the openwatersio/seamap pipeline as a separate tile source.

```
Pass 1  inventory (DSID + M_COVR) → coverage resolver ("best scale wins", grid-indexed mask)
Pass 2  per cell, parallel: read → units to metres → M_NSYS inheritance → master/slave
        aggregation → tags (YAML tables) → clip (points: buffered effective area + seam flag;
        lines/areas: exact intersection) → points in memory, lines/areas spooled to sqlite
Final   seam dedup (points) → dropped-object audit → line/area re-join → writer (pyosmium)
```

Package `enc2osm/` (CLI `enc2osm build | inventory | lnam-check`), Dockerfile on the pinned
`ghcr.io/osgeo/gdal:ubuntu-small-3.13.3` (arm64 verified), 102 tests, one commit series per
phase on `dev`, tag `v0.1.0`. Runtime dependencies: GDAL bindings + pyosmium only (YAML via a stdlib parser,
temp store via stdlib sqlite3).

How to run: see `README.md`. Short version:

```sh
docker build -t enc2osm .
docker run --rm -v "$PWD":/work -w /work enc2osm build -o out.osm.pbf --classes v2 \
    --workers 4 --report report/ ENC_ROOT/
scripts/preview.sh            # San Francisco test region → out/preview/enc-sf.osm.pbf
```

**Fixtures** (DECISIONS D2/D3): *small* = San Francisco, 14 NOAA cells, bands 1–5 (committed,
12 MB) plus one golden-only cell (US3WA1EF); *medium* = Puget Sound, 90 cells (1×b1, 1×b2, 4×b3,
12×b4, 72×b5), 17.2 MB zipped, downloaded by `scripts/fetch_fixtures.py medium`.
NOAA has **no** same-band overlap anywhere (checked all 7114 active cells) → that case is covered
by synthetic tests.

## 2. Acceptance criteria

All numbers: medium fixture, `--workers 4`, inside the Docker image, unless stated otherwise.

| # | Criterion | Result |
|---|---|---|
| 1 | Unit, seam-scenario, golden tests green in the image | **PASS** — 102 passed (`scripts/dev.sh pytest -q`), incl. 51 golden cases (34 v1 + 17 v2), 10 seam scenarios |
| 2 | `osmium fileinfo -e` / `check-refs` clean | **PASS** — v1: 18,858 nodes / 522 ways / 15 relations; v2: 156,886 / 2,341 / 72; "Objects ordered: yes"; check-refs: 0 missing nodes/ways/relations |
| 3 | Coverage invariants (`scripts/check_acceptance.py`) | **PASS** — 8,140 points and 1,627 lines/areas all inside their (buffered) effective areas; union(effective) Δ union(M_COVR) = 0.0 deg²; overlap of effective areas 9.7e-13 deg² (float noise, ≈ 0.01 m²); 0 slivers dropped |
| 4 | Dedup invariant, ambiguous < 1 % | **PASS** — 0 cross-cell same-type/same-name pairs within 100 m; 0 ambiguous of 202 seam candidates (0 %); 15 seam merges. 6 same-name pairs exist *within one cell* (distinct S-57 objects, listed in §7, D17) |
| 5 | No orphaned slaves | **PASS** — LIGHTS 1389 read = 1378 on a structure + 11 standalone; TOPMAR 4 = 4 + 0; FOGSIG 139 = 139 + 0; DAYMAR 471 = 470 + 1; RTPBCN 9 = 9 + 0 |
| 6 | `--workers 1` ≡ `--workers 4` byte-identical | **PASS** — v1 and v2 (sha256 v2 `a92dcff2…`), also identical with the vertex store forced to sqlite |
| 7 | Performance + full-NOAA estimate | see §4 — medium v2: 2.5 s wall, 166 MB peak RSS, 90 cells, 17,865 features |
| 8 | Dropped-object audit | 285 (v1) / 286 (v2) without counterpart, **16 examined, 0 bugs** — see §5 |
| 9 | No free-text leakage | **PASS** — every `seamark:type` and every enumerated value is in the mapping tables |
| 10 | Reference style tags covered, three traps decided | see §6 and DECISIONS D12, D15 |

v1 and v2 numbers side by side (medium):

| | v1 | v2 |
|---|---|---|
| features read | 15,432 | 17,865 |
| points kept before / after dedup | 8,127 / 8,112 | 8,155 / 8,140 |
| seam candidates / merges / ambiguous | 201 / 15 / 0 | 202 / 15 / 0 |
| points dropped by clipping | 4,457 | 4,470 |
| lines/areas before / after re-join | 511 / 502 | 1,966 / 1,617 |
| re-joined: area pieces → features, line pieces → features | 4 → 2, 11 → 4 | 325 → 92, 169 → 53 |

Small fixture (v2): 14 cells, 2,362 points, 791 lines/areas, 8 seam merges, 0 ambiguous, all
checks PASS.

## 3. Plausibility against OSM (metric)

Existing OSM seamark nodes in the medium region (Overpass, 2,381 nodes, OSM base
2026-10-23T06:12Z) matched 1:1 to the v1 output by nearest distance ≤ 100 m: 820 pairs.

| Attribute | Agree | Disagree | Rate |
|---|---|---|---|
| `seamark:type` | 368 | 452 | 44.9 % |
| colour (same type) | 38 | 5 | 88.4 % |
| shape (same type) | 22 | 14 | 61.1 % |
| light character | 87 | 2 | 97.8 % |

Systematic disagreements (> 5 %) investigated — **none is a mapping error**:

- **type `mooring` ↔ OSM `pile` (154)**, `obstruction` ↔ `pile` (92), `obstruction` ↔ `mooring`
  (24): the ENC encodes dolphins as MORFAC CATMOR=1 (wiki: `mooring` + `category=dolphin`) and
  snags/stumps as OBSTRN CATOBS=1; OSM mappers tag the same piles as `seamark:type=pile`.
- **`buoy_special_purpose` ↔ OSM `light_minor` (14) / `buoy_lateral` (10)**: OSM maps lit buoys
  as standalone lights, and the yellow Puget Sound TSS buoys ("Traffic Separation Lane Lighted
  Buoy TC", CATSPM, yellow) as `buoy_lateral` with colour yellow — internally inconsistent in OSM.
- **shape** `conical` ↔ `pillar`: e.g. "Lake Union Shoal Buoy 2" is BOYSHP=1 (nun) in the ENC,
  `pillar` in OSM; "Smith Cove Lighted Buoy 3" BOYSHP=4 (pillar, lighted) vs. `can` in OSM.
  The ENC values were taken verbatim through the code table.
- colour: 5 disagreements (e.g. ENC `white;orange` regulatory buoys vs OSM `white`).

Pairs: `report/plausibility_pairs.csv` (script `scripts/plausibility.py`).

## 4. Performance (criterion 7)

MacBook Air (Apple Silicon), Docker (arm64), medium fixture, wall times from the tool:

| Run | pass 1 | pass 2 | finalize | total | peak RSS |
|---|---|---|---|---|---|
| v1, 4 workers | 0.8 s | 0.8 s | 0.2 s | 1.8 s | 118 MB |
| v1, 1 worker | 0.5 s | 1.9 s | 0.1 s | 2.5 s | 121 MB |
| v2, 4 workers | 0.5 s | 1.0 s | 1.1 s | 2.5 s | 166 MB |
| v2, 1 worker | 0.5 s | 2.6 s | 1.1 s | 4.1 s | 168 MB |

Measured building blocks: the coverage resolver on **all 7,114 active NOAA coverages** (catalog
panels) takes 0.7 s / 109 MB; one point object ≈ 1 KB (tracemalloc); a worker on the largest
NOAA cell (US3WA1EF, 1.8 MB zipped — it is in the medium fixture) peaks at ~100 MB; sqlite vertex
lookups cost ~7 µs per vertex (148,746 vertices: +1.1 s).

**Full NOAA estimate** (7,114 active cells, 0.79 GB zipped = 46× the medium fixture by volume,
79× by cell count; the medium region is dense, so the range is conservative):

| | estimate (46× … 79×) |
|---|---|
| wall time, v2, 4 workers | ≈ 2–4 min (pass 1 ≈ 0.5 min, pass 2 ≈ 1–1.5 min, finalize ≈ 1–2 min incl. ≈ 0.5–1 min sqlite vertex lookups for the 4–9 M vertices beyond the 3 M in-memory threshold) |
| points in memory | ≈ 0.6–1.0 M objects → ≈ 0.6–1.0 GB (dropped points keep only type/name) |
| peak RSS | ≈ 1.5–2 GB (main ≈ 1–1.6 GB: points + ≤ 3 M in-memory vertices; 4 workers ≈ 0.1–0.3 GB each) → **within 4 GB** |

**Expected bottleneck:** the single-threaded finalize step — memory for all seamark points held
for dedup (by design, CLAUDE.md Phase 6) and time for vertex deduplication once it spills to
sqlite. Pass 2 parallelises linearly with workers; pass 1 and the resolver are negligible.
Not measured: I/O for 7,114 files and the GDAL read time of the many tiny band-5 cells
(median 0.06 MB), which could shift time towards pass 1.

## 5. Dropped-object audit (criterion 8)

Points clipped because a higher-priority cell covers their position, without a counterpart in
the output (same type within 100 m or same type + name within 1 km): **285 (v1), 286 (v2)** of
4,457 / 4,470 clipped. Breakdown by type: 152 position, 31 type, 84 "covering cell older",
18 "covering cell newer" (`scripts/classify_dropped.py` heuristic). By class: piles 98, rocks 105,
obstructions 38, landmarks 13, moorings 16, wrecks 15 — **no buoy, beacon, light or other aid to
navigation.** Covering pairs: band 3 under band 4 (174), band 3 under band 5 (95), band 4 under
band 5 (15), band 1 under band 2 (1).

16 cases examined against the raw S-57 data of both cells (`scripts/near.py`):

| # | Dropped (cell, class, LNAM) | Covering cell finding | Class |
|---|---|---|---|
| 1 | US3WA1DF PILPNT 0226C3F4A6DDE2FD | US4WA1FI pile 164 m away (sources 2005 vs 2016) | position difference |
| 2 | US3WA1EG PILPNT 0226C4819215E2FD | US4WA1IK pile, CATPLE=3, 196 m away | position difference |
| 3 | US3WA1DF UWTROC 0226C3EF24CEE2FD | US4WA1FI rock, WATLEV=4, 107 m away | position difference |
| 4 | US3WA1DF PILPNT 0226247218BBE2FD | US5SEAJK BCNSPP 29 m away (structure charted as beacon) | edition/content (encoding) |
| 5 | US3WA1DF WRECKS 02264E1DA193E2FD (VALSOU 9.6, SORDAT 2007-04-14) | US5SEACK OBSTRN 54 m, VALSOU 9.7, same SORDAT | edition/content (encoding) |
| 6 | US3WA1DF PILPNT 0226C13F7813E2FD | US5SEACJ OBSTRN CATOBS=1 (stump) 12 m | edition/content (encoding) |
| 7 | US3WA1EF PILPNT 022690E8CDBBE2FD | US4WA1IJ ruined OBSTRN stumps 67–100 m | edition/content (encoding) |
| 8 | US3WA1DF PILPNT 0226621A90CDE2FD | US5SEADJ OBSTRN 32 m + ruined SLCONS | edition/content (encoding) |
| 9 | US3WA1DF PILPNT 02263B16924BE2FD | US5SEAEJ: obstructions 138–164 m, wreck 128 m (2014 survey), no pile | edition/content |
| 10 | US3WA1EF UWTROC 022641C2E45CE2FD | US4WA1II: nothing within 300 m | edition/content |
| 11 | US3WA1EF PILPNT 02264B5F1B5AE2FD | US4WA1IJ: nearest pile 1.1 km | edition/content |
| 12 | US3WA1EF UWTROC 02260FEC325CE2FD | US5SEALJ: only shoreline construction | edition/content |
| 13 | US3WA1DF UWTROC 02269B35CE63E2FD | US5SEAFJ (issued 2026-09-08): no rock within 300 m | edition/content |
| 14 | US4WA1IJ UWTROC 0226D7AFCB63A2D0 | US5SEALJ: none | edition/content |
| 15 | US4WA1IJ UWTROC 02263FE4D757A2D0 | US5SEALJ: none | edition/content |
| 16 | US3WA1DF LNDMRK 02264271CEF5E2FD (dome) | US5SEAAK: none | edition/content |

Result: 3 position differences beyond tolerance, 13 content differences between the products
(5 of them the same object encoded as a different class), **0 bugs**. The small band-3 objects
mostly carry 2005–2010 sources while the band-5 cells were compiled from 2014+ surveys, so
"best scale wins" is the intended behaviour; OPEN_QUESTIONS Q7 asks whether hazards without a
higher-band counterpart should be kept anyway.

## 6. Tags read by the reference pipeline (criterion 10)

Source: `Seamark.java`, `Lights.java`, `SeamarkZoomRules.java`, `SeamarkPriority.java` and
`style/layers/*.ts` of openwatersio/seamap @ 5741624 (2026-10-23).

| Read by the reference | Produced? | Notes |
|---|---|---|
| `seamark:type` | yes | 40 types in `objects.yaml`/`rules.yaml` |
| `seamark:<type>:name`, `seamark:name`, `name` | `seamark:name` | wiki: OBJNAM → seamark:name |
| `seamark:<type>:category` | yes (6,088×) | all CAT* attributes |
| `seamark:<type>:function` | yes (landmarks) | FUNCTN |
| `seamark:<type>:shape`, `:colour`, `:colour_pattern` | yes | BOYSHP/BCNSHP/TOPSHP, COLOUR, COLPAT |
| `seamark:light:*` incl. `light:N:*`, `sector_start/end`, `range`, `character`, `group`, `period`, `height`, `category`, `multiple`, `visibility` | yes | numbering rule D12 |
| `seamark:fog_signal:category/group/period` | yes | |
| `seamark:topmark:*`, `seamark:daymark:colour/shape` | yes | |
| `seamark:radar_transponder:category/group` | yes | RTPBCN |
| `seamark:<type>:reflectivity` | yes | CONRAD |
| `seamark:radar_reflector` | **no** | RADRFL is not in scope (v1/v2 lists) |
| `seamark:radio_station:*` | **no** | RDOSTA (AIS etc.) not in scope; refs counted `ref_unresolved` (46) |
| `seamark:<type>:depth` | yes (1,068×) | VALSOU in metres |
| `seamark:wreck:category`, `:water_level` | yes | |
| `seamark:rock:water_level` | yes | also `seamark:obstruction:water_level` (wiki); the style reads the rock key and the generic `seamark:water_level`, so obstruction water levels are not used by the style |
| `seamark:landmark:conspicuity` | yes | CONVIS |
| `seamark:<type>:restriction` | partly (61×) | RESTRN lists with supplement codes 16–27 are dropped entirely (OPEN_QUESTIONS Q1) |
| `seamark:pipeline_submarine:category/product` | yes (v2) | |
| `seamark:seabed_area:surface` | **no** | SBDARE not in scope |
| `seamark:shoreline_construction:water_level` | **no** | SLCONS not in scope |
| plain keys (`ref`, `operator`, `fuel`, `leisure=marina`, …) | **no** | OSM-only concepts, nothing in S-57 maps to them |
| `seamark:lnam`, `seamark:source` | not emitted | the pipeline denylists them; provenance is in `enc:*` |

The three known traps (DECISIONS D12, D15):

1. **Lighthouses** → master type stays (`landmark` + `category=tower` + `function=light_support`)
   with `seamark:light:*` on the same node. The reference has explicit "lit landmark" handling
   (light label, flare, z6 promotion), and major/minor rendering comes from `light_range`.
2. **Area vs. line** → Planetiler 0.10.2 treats any closed way as a polygon unless `area=no`;
   areas are closed ways / multipolygon relations, closed linear ways get `area=no`
   (4× in medium v2), `ALWAYS_LINEAR` types are lines anyway.
3. **Light character** → `LITCHR` → wiki abbreviations (`Fl`, `Q`, `Iso`, `Al.Fl`, `Q+LFl`, …),
   `SIGGRP` "(3)" → `group=3`, `SIGPER` → `period`, `HEIGHT` → `height`, `VALNMR` → `range`;
   `Seamark.lightAbbr` composes `Fl(3)…30s47m19M` from these. Light characters agree with OSM
   in 97.8 % of matched pairs.

## 7. LNAM check (informational)

`enc2osm lnam-check`: share of LNAMs (BOY*/BCN*/LIGHTS) occurring in more than one cell —
small: 316 of 1,106 (28.6 %); medium: 864 of 1,836 (47.1 %), e.g. LIGHTS 397 of 848,
BCNSPP 200 of 397. NOAA does reuse LNAMs across bands for the same object frequently, but not
always; no design decision depends on it (dedup is position/attribute based).

Same-name pairs inside one cell (criterion 4 transparency, medium): "Acoustic recorder"
(US3WA1EF, 80 m), "Bainbridge Island Boat Yard Light A" (US5SEAFJ, 66 m), "Elliott Bay Fish Pen
Light B" (US5SEAFL, 39 m), "Bangor South Floating Security Barrier Light" (US5SEAHG, 86 m),
"Edmonds Fishing Reef Buoy" (US5SEAIL, 40 m), "Meydenbauer Yacht Club Mooring Pier Light"
(US5SEAJH, 62 m) — all distinct objects in the source cell.

## 8. Deviations from CLAUDE.md (need review)

1. **Positive object IDs by default** (D16). Negative IDs make Planetiler 0.10.2 abort
   ("Nodes must be sorted ascending by ID"); `--negative-ids` keeps the specified behaviour.
2. **Seam dedup "unique match"** is implemented as greedy 1:1 matching with a same-cell rival
   test, and pairs from merely touching cells only merge at ≤ 1 m (D13). The literal rule would
   have produced 9.4 % ambiguous pairs and one wrong merge (two rocks 40 m apart) on the small
   fixture.
3. **Criterion 4 check** counts cross-cell pairs only (D17).
4. Mapping rules live in a fourth table `rules.yaml` (standalone light rule).
5. v1 classes that also occur as lines/areas (LNDMRK, MORFAC, WRECKS, OBSTRN) are emitted through
   the line/area path already with `--classes v1` (D15).

## 9. Known limitations

- Cells crossing the antimeridian (Aleutians, Guam/CNMI) are out of scope.
- Unconfirmed enumeration codes (S-57 supplements) and unclear units are dropped, not guessed
  (OPEN_QUESTIONS Q1–Q5); e.g. most cable/pipeline areas lose `restriction`.
- Dedup cannot tell two identical unnamed marks ≤ 50 m apart across a seam of overlapping cells
  from one mark with a position offset when each cell charts only one of them (D13).
- Asynchronous editions: objects only in an older/lower band are dropped where a higher band
  covers (§5); they are reported, not restored.
- `SCAMIN` is passed through as `enc:scamin` but not used for zoom levels (the reference
  pipeline computes its own).
- Slaves of non-point masters (lit landmark polygons, lights on bridge lines) and of out-of-scope
  masters (e.g. BUISGL) become standalone light nodes.
- Not done in this run: a full NOAA build, a render through the SeaMap pipeline (Planetiler was
  checked at source level only; `scripts/preview.sh` prepares it), visual check against the NOAA
  chart viewer.

## 10. Full NOAA build (after v0.1.0)

All 7,114 active NOAA cells (catalog of 2026-10-23, 0.79 GB zipped, 1.9 GB unpacked; downloaded with
`scripts/fetch_fixtures.py --all`), `--classes v2 --workers 4`, Docker image on the MacBook Air.
The cells were streamed into a Docker volume: two earlier attempts through the bind-mounted project
directory made Docker Desktop's file-sharing service fail ("service fs failed: injecting event
blocked for 60s"); that is a Docker Desktop problem, not one of enc2osm.

**Time and memory** (memory from cgroup v2 inside the container):

| | estimate (§4) | measured |
|---|---|---|
| wall time | 2–4 min | **3:18 min** — pass 1 23 s, pass 2 60 s, finalize 115 s |
| process memory (anon, peak) | 1.5–2 GB | **2.0 GB** (+ 0.75 GB file cache) — within 4 GB |

The single-threaded finalize step is the bottleneck, as predicted.

**Output:** `noaa_v2.osm.pbf`, 33 MB — 379,856 seamark nodes, 6.3 M way vertices, 117,862 ways,
4,703 relations, from 750,836 features read.

| Metric | Value |
|---|---|
| points kept before / after dedup | 380,235 / 379,856 |
| seam candidates / merges / ambiguous | 8,805 / 379 / 6 (0.07 %) |
| points dropped by clipping / without counterpart | 145,549 / 18,093 |
| lines/areas before / after re-join | 100,214 / 80,766 (16,944 area pieces → 4,001, 9,980 line pieces → 3,475) |
| tag values shortened to 255 chars | 252 (155 `enc:lnam`, 34 `enc:cell`, 55 `restricted_area:information`, …) |

**Acceptance checks on the full output** — all PASS:
`osmium check-refs` clean; criterion 3: 379,856 points and 81,236 lines/areas inside their
effective areas (34 with a shortened `enc:cell` list checked against the union of all effective
areas), union difference 1.1e-9 deg² ≤ dropped-sliver bound 4.5e-8 deg², overlap −7.7e-10 deg²
(float noise); criterion 4: 0 cross-cell violations, 6 ambiguous of 8,805 (0.07 %), 395
same-name pairs inside single cells; criterion 5: e.g. LIGHTS 46,628 = 46,077 on a structure +
551 standalone, 0 orphaned; criterion 9: no unknown types or values.

**Bugs found by the full build and fixed** (DECISIONS D19, tests added):

1. Tag values over the OSM limit of 255 characters crashed the writer (provenance lists of
   features re-joined from many cells, long `information` texts).
2. The re-join tolerance was converted to degrees once at the highest latitude of *all* cells
   (72° N) → ~140 m instead of 50 m in Texas; a pipeline was joined across a third cell's corner.
   Now converted per pair at its own latitude.
3. The same named mark occurs in two *touching* same-band cells 48–99 m apart (asynchronous
   editions, sometimes the same LNAM, e.g. "Whittaker Creek Buoy 3" in US5NC2CF/US5NC2DF). Named
   marks of the same type are now matched up to 2× tolerance between any cells; unnamed marks keep
   the stricter rule.
4. Report generation looked up the covering cell for each dropped object over all cells
   (~4 min); now grid-indexed.
5. The criterion-3 check used a fixed 1e-9 deg² threshold, stricter than the documented sliver
   tolerance; it now uses the bound of the slivers actually dropped.

**Still open:**

- The 18,093 dropped objects without counterpart are **not yet classified** for the full set.
  By type: rock 12,352, obstruction 2,217, wreck 1,902, pile 838, landmark 446, mooring 141,
  platform 113, anchorage 19 — and, unlike on the fixtures, **58 aids to navigation**
  (38 `beacon_special_purpose`, 13 `buoy_special_purpose`, 4 `daymark`, 3 `light_minor`).
  Most frequent band pairs: 3 under 4 (8,610), 4 under 5 (3,414), 2 under 4 (2,360), 3 under 5
  (2,170). The aids to navigation should be examined first (`report/dropped_without_counterpart.csv`).
- Further S-57 supplement codes appear nationally (OPEN_QUESTIONS Q1): RESTRN 16–27, CATREA 27/28,
  CATSPM 53–56, CATACH=10, CATOBS=10, CATLMK=21, WATLEV=7.
- The output bbox spans −180…180°: antimeridian cells (Aleutians, Guam/CNMI) are still out of
  scope and should be checked or excluded before rendering.

