# Progress

| Phase | Status | Verified |
|---|---|---|
| 0 Scaffold + LNAM experiment | done | image builds (arm64), fixtures fetched (small 14 cells, medium 90 cells), `lnam-check` runs, tests green |
| 1 Inventory | done | `inventory` on small (14 cells, bands 1–5) + medium (90 cells); tests: CATCOV union/hole, missing M_COVR, duplicate name, broken file |
| 2 Coverage resolver | done | synthetic: nested, partial, same-band (scale, date, name), shadowed, sliver; small+medium: union(eff)=union(cov), no overlap |
