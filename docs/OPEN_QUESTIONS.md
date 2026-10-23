# Open questions

Everything here is deliberately **left unmapped** (dropped, or kept as `enc:<ACRONYM>` with
`--keep-raw`) and counted in `report/stats.json` (`unmapped_attr:*`, `unmapped_value:*`).
Counts are from the medium fixture (Puget Sound, 90 cells, `--classes v2`).

## Q1 — Enumeration codes from S-57 supplements, missing in GDAL's table

GDAL 3.13.3 `s57expectedinput.csv` stops at the S-57 Ed. 3.1 base values. NOAA cells use newer
codes. The OSM wiki lists further values *without numeric codes*; the order suggests the mapping
below, but that is a guess from list order, so nothing is mapped until confirmed against IHO S-57
Supplement 3 (Ed. 3.1.2) / the IHO Object Catalogue.

| Code | Count | Likely meaning (wiki order, unconfirmed) | Candidate OSM value |
|---|---|---|---|
| RESTRN=24 | 315 | dragging prohibited | `no_dragging` |
| RESTRN=20 | 6 | drilling prohibited | `no_drilling` |
| RESTRN=27 | 6 | speed restricted | `restricted_speed` |
| RESTRN=18 | 2 | industrial/mineral exploration prohibited | `no_exploration_development` |
| CATOBS=10 | 113 | boom | `boom` |
| WATLEV=7 | 116 | floating | `floating` |
| CATSPM=55 | 26 | ? | ? |
| CATSPM=56 | 4 | ? | ? |
| CATREA=27 | 3 | ? (wiki after 25: water_skiing, essa) | ? |
| CATLMK=21 | 1 | ? (wiki has `boulder` first) | ? |

Effect today: an object with such a list value loses the **whole** attribute (never a partial list),
e.g. most cable/pipeline areas have `RESTRN=[2,6,24]` and therefore no `restriction` tag.
**Action:** confirm codes, then add to `values.yaml` + golden tests.

## Q2 — Units of HORCLR, RADIUS, BURDEP
HORCLR (bridge clearance width, 111×), RADIUS (anchor berth radius) and BURDEP are lengths, but it
is unclear whether they follow `DSPM_HUNI`, are always metres, or use `PUNI`. Unmapped until clarified.

## Q3 — DSPM_DUNI = 2 ("fathoms and feet")
Value encoding unclear (decimal fathoms? fathoms.feet?). Depth attributes of such cells are dropped
and counted (`unit_unknown:*`). No NOAA fixture cell uses it.

## Q4 — Signal groups with several brackets
`SIGGRP` like `(6)(1)` (2× in LIGHTS, with LITCHR=25 Q+LFl). The style composes `Q(6)+LFl` from
`group=6`; whether `6` or `6)(1` is intended in OSM is not documented → unmapped.

## Q5 — Object classes / values without an OSM equivalent on the wiki
- `DWRTPT` (deep water route part): no `seamark:type` on the wiki → not converted.
- `CATBRG=8` (transporter bridge): wiki row has no value → unmapped.
- Attributes without a wiki key: `EXPSOU` (1586×), `QUASOU` (7042×), `TECSOU` (16×), `VERDAT`,
  `VERACC`, `DATSTA`/`DATEND` (2×). Text/graphics references `TXTDSC` (82×), `PICREP`, `NTXTDS`
  and national-language `NOBJNM` (22×)/`NINFOM` (7×) are dropped too.

## Q6 — Decisions that deviate from CLAUDE.md or need a human check
- **Positive object IDs by default** (DECISIONS D16): negative IDs break Planetiler.
- **Lighthouse typing** (D12): `landmark` + `seamark:light:*`, not `light_major`. Please check the
  rendering of e.g. Alcatraz Light / Point Blunt Light in the SeaMap preview.
- **Standalone light without VALNMR → `light_minor`** (rules.yaml): matches the style's 9 M default.
- **Dedup between touching (non-overlapping) cells only at ≤ 1 m** (D13).

## Q7 — Dropped objects without counterpart
286 hazards/landmarks/piles from bands 3–4 are clipped where a band-4/5 cell has none within
2× tolerance (no aids to navigation among them). Examined sample: position offsets of 100–500 m,
encoding differences (wreck ↔ obstruction, pile ↔ obstruction) and objects the larger-scale cell
does not chart. See REPORT.md, criterion 8. Whether some should be kept (e.g. "keep lower-band
hazards if the higher band has nothing within X m") is a product decision.
