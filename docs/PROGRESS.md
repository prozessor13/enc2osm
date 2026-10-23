# Progress

| Phase | Status | Verified |
|---|---|---|
| 0 Scaffold + LNAM experiment | done | image builds (arm64), fixtures fetched (small 14 cells, medium 90 cells), `lnam-check` runs |
| 1 Inventory | done | small (14 cells, bands 1–5) + medium (90); tests: CATCOV union/hole, missing M_COVR, duplicate name, broken file |
| 2 Coverage resolver | done | synthetic: nested, partial, same-band (scale, date, name), shadowed, sliver; fixtures: union(eff)=union(cov), no overlap; full NOAA catalog (7114 cells) in 0.7 s |
| 3 Feature extraction | done | units (m/ft/fathoms, unknown → dropped+counted), M_NSYS inheritance; YAML loader = PyYAML on all tables |
| 4 Master/slave aggregation | done | LNAM refs both directions, unique position fallback, standalone grouping, light order |
| 5 Tag mapping (v1) | done | 34 hand-derived golden cases |
| 5b Tag mapping (v2) | done | 17 hand-derived golden cases |
| 6 Clipping, seam dedup, re-join | done | 10 seam scenarios; medium: 15 merges, 0 ambiguous |
| 7 OSM writer | done | own node per seamark, vertex dedup (sqlite spill), way split 2000, multipolygons, `area=no`; positive IDs (D16) |
| 8 CLI, stats, packaging | done | e2e CLI tests, wheel/Docker entry point verified, README, preview.sh |
| Acceptance | done | criteria 1–10, see REPORT.md (medium v1 + v2, small v2) |

Final state of v0.1.0: 102 tests green in the image; tag `v0.1.0`.

| Full NOAA build | done | 7,114 cells in 3:18 min, 2.0 GB; checks 3/4/5/9 PASS after 5 fixes (D19); 105 tests; dropped objects not yet classified (REPORT §10) |
