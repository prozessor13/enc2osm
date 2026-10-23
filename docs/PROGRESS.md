# Progress

| Phase | Status | Verified |
|---|---|---|
| 0 Scaffold + LNAM experiment | done | image builds (arm64), fixtures fetched (small 14 cells, medium 90 cells), `lnam-check` runs, tests green |
| 1 Inventory | done | `inventory` on small (14 cells, bands 1–5) + medium (90 cells); tests: CATCOV union/hole, missing M_COVR, duplicate name, broken file |
| 2 Coverage resolver | done | synthetic: nested, partial, same-band (scale, date, name), shadowed, sliver; small+medium: union(eff)=union(cov), no overlap |
| 3 Feature extraction | done | units (m/ft/fathoms, unknown → dropped+counted), M_NSYS inheritance (own wins, conflict → unset), small cell read; YAML loader = PyYAML on all tables |
| 4 Master/slave aggregation | done | synthetic: LNAM refs both directions, unique position fallback, ambiguous position, area master, standalone grouping, light order; fixtures: 3057 attached by LNAM, 10 by position, 41 standalone groups |
