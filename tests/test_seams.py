"""Synthetic seam scenarios: clipping (PointClipper) + seam dedup + area/line re-join.

Layout: LO (band 4) covers x in [0, 0.02]; HI (band 5) covers x in [0.01, 0.02]. The effective
boundary between them is x = 0.01 (HI to the east). Latitude ~0 -> 1e-5 deg ~ 1.11 m.
"""

from osgeo import ogr
from test_coverage import box, cell

from enc2osm import coverage, dedup
from enc2osm.build import CoverageOverlap
from enc2osm.pass2 import PointClipper, PointObj, ShapeObj
from enc2osm.rejoin import rejoin

TOL = 50.0
DEG_PER_M = 1 / 111_320.0
BX = 0.01  # boundary


def setup():
    cells = [cell("LO", 4, box(0, 0, 0.02, 0.02)), cell("HI", 5, box(BX, 0, 0.02, 0.02))]
    effs = coverage.resolve(cells)
    tol_deg = coverage.m_to_deg(TOL, 0.02)
    clip = {c.name: PointClipper(effs[c.name].geom, tol_deg) for c in cells}
    return cells, effs, clip


def run(objs):
    """objs: (cell, lnam, x_offset_m_from_boundary, tags) -> written points."""
    cells, effs, clip = setup()
    pts = []
    for cname, lnam, off_m, tags in objs:
        x, y = BX + off_m * DEG_PER_M, 0.01
        st = clip[cname].status(x, y)
        if st == "drop":
            continue
        pts.append(PointObj(cname, effs[cname].rank, "BOYLAT", lnam, x, y, dict(tags),
                            seam=st == "seam"))
    kept, decisions = dedup.dedup(pts, TOL, 0.2 * TOL, overlaps=CoverageOverlap(cells, 10.0))
    return kept, decisions


BUOY = {"seamark:type": "buoy_lateral", "seamark:buoy_lateral:colour": "red",
        "seamark:buoy_lateral:shape": "can"}


def test_same_buoy_offset_20m_across_boundary_both_directions():
    # HI's version on the LO side, LO's version on the HI side (both are 'guests')
    kept, dec = run([("HI", "h", -10, BUOY), ("LO", "l", +10, BUOY)])
    assert [(p.cell, p.lnam) for p in kept] == [("HI", "h")]
    # and the other way round (both inside their own effective areas)
    kept, dec = run([("HI", "h", +10, BUOY), ("LO", "l", -10, BUOY)])
    assert [(p.cell, p.lnam) for p in kept] == [("HI", "h")]
    assert [d.action for d in dec] == ["merged"]


def test_same_buoy_deep_inside_hi_is_not_lost():
    # LO's copy 60 m inside HI's area is clipped, HI keeps its own: exactly once
    kept, _ = run([("HI", "h", 55, BUOY), ("LO", "l", 60, BUOY)])
    assert [(p.cell, p.lnam) for p in kept] == [("HI", "h")]


def test_two_different_unnamed_buoys_30m_apart_both_survive():
    # A on the LO side (charted by LO only: outside HI's coverage), B on the HI side
    # (charted by HI and, as in real ENCs, also by LO). Identical attributes.
    kept, dec = run([("LO", "A", -15, BUOY), ("LO", "B_lo", +15, BUOY), ("HI", "B", +15, BUOY)])
    assert sorted((p.cell, p.lnam) for p in kept) == [("HI", "B"), ("LO", "A")]


def test_different_attributes_never_merge():
    green = dict(BUOY, **{"seamark:buoy_lateral:colour": "green"})
    kept, dec = run([("LO", "A", -15, BUOY), ("HI", "B", +15, green)])
    assert len(kept) == 2 and dec == []


def test_named_marks_match_by_name_only():
    a = dict(BUOY, **{"seamark:name": "Buoy 1"})
    b = dict(BUOY, **{"seamark:name": "Buoy 2"})
    kept, _ = run([("LO", "x", -10, a), ("HI", "y", +10, b)])
    assert len(kept) == 2
    kept, _ = run([("LO", "x", -10, a), ("HI", "y", +10, a)])
    assert [(p.cell, p.lnam) for p in kept] == [("HI", "y")]


def test_ambiguous_pair_keeps_both():
    # one HI buoy, two identical LO buoys at the same distance on either side -> can't tell
    cells, effs, clip = setup()
    y0 = 0.01
    hi, lo = effs["HI"].rank, effs["LO"].rank
    mk = [PointObj("HI", hi, "BOYLAT", "h", BX + 5 * DEG_PER_M, y0, dict(BUOY), True),
          PointObj("LO", lo, "BOYLAT", "l1", BX - 15 * DEG_PER_M, y0, dict(BUOY), True),
          PointObj("LO", lo, "BOYLAT", "l2", BX + 5 * DEG_PER_M, y0 + 20 * DEG_PER_M,
                   dict(BUOY), True)]
    kept, dec = dedup.dedup(mk, TOL, 0.2 * TOL, overlaps=CoverageOverlap(cells, 10.0))
    assert len(kept) == 3 and {d.action for d in dec} == {"ambiguous"}


def test_touching_cells_merge_only_identical_positions():
    cells = [cell("W", 5, box(0, 0, BX, 0.02)), cell("E", 5, box(BX, 0, 0.02, 0.02))]
    ov = CoverageOverlap(cells, 10.0)

    def mk(c, lnam, off):
        return PointObj(c, 0 if c == "E" else 1, "BOYLAT", lnam, BX + off * DEG_PER_M, 0.01,
                        dict(BUOY), True)

    kept, _ = dedup.dedup([mk("W", "w", -20), mk("E", "e", 20)], TOL, 10, overlaps=ov)
    assert len(kept) == 2  # 40 m apart in non-overlapping cells: two marks
    kept, _ = dedup.dedup([mk("W", "w", 0), mk("E", "e", 0)], TOL, 10, overlaps=ov)
    assert len(kept) == 1  # same mark encoded at the shared edge of both


def _shape(cell_name, wkt, kind="area", **extra):
    g = ogr.CreateGeometryFromWkt(wkt)
    tags = {"seamark:type": "anchorage", "enc:cell": cell_name, "enc:band": "5",
            "enc:lnam": cell_name + "1", **extra}
    return ShapeObj(cell_name, 0, "ACHARE", cell_name + "1", kind, bytes(g.ExportToWkb()), tags)


def test_area_split_by_boundary_is_rejoined():
    a = _shape("LO", box(0.0, 0.0, BX, 0.005))
    b = _shape("HI", box(BX, 0.0, 0.015, 0.005))
    merged, st = rejoin([a, b], TOL)
    assert len(merged) == 1 and st["rejoined_area_features"] == 1
    assert abs(ogr.CreateGeometryFromWkb(merged[0].wkb).GetArea() - 0.015 * 0.005) < 1e-12
    assert merged[0].tags["enc:cell"] == "HI;LO"


def test_area_rejoin_requires_identical_tags_and_different_cells():
    a = _shape("LO", box(0.0, 0.0, BX, 0.005))
    b = _shape("HI", box(BX, 0.0, 0.015, 0.005), **{"seamark:name": "X"})
    c = _shape("LO", box(BX, 0.006, 0.015, 0.01))
    merged, _ = rejoin([a, b, c], TOL)
    assert len(merged) == 3


def test_line_split_by_boundary_is_rejoined():
    a = _shape("LO", f"LINESTRING(0 0.005, {BX} 0.005)", "line")
    b = _shape("HI", f"LINESTRING({BX + 1e-6} 0.005, 0.02 0.006)", "line")
    merged, st = rejoin([a, b], TOL)
    assert len(merged) == 1
    g = ogr.CreateGeometryFromWkb(merged[0].wkb)
    assert g.GetGeometryCount() == 1 and g.GetGeometryRef(0).GetPointCount() == 4


def test_rejoin_tolerance_is_metric_at_each_latitude():
    # two area pieces 100 m apart at 29 N must not join with a 50 m tolerance, even when the
    # group also contains features far north (bug: one global conversion at the max latitude)
    gap = 100 / (111_320 * 0.875)  # ~100 m in longitude at 29 N
    a = _shape("LO", box(0.0, 29.0, 0.01, 29.01))
    b = _shape("HI", box(0.01 + gap, 29.0, 0.02, 29.01))
    far = _shape("AK", box(0.0, 72.0, 0.01, 72.01))
    merged, _ = rejoin([a, b, far], TOL)
    assert len(merged) == 3


def test_named_mark_in_touching_cells_up_to_twice_tolerance():
    # same named buoy charted 75 m apart in two neighbouring same-band cells (async editions)
    cells = [cell("W", 5, box(0, 0, BX, 0.02)), cell("E", 5, box(BX, 0, 0.02, 0.02))]
    ov = CoverageOverlap(cells, 10.0)
    named = dict(BUOY, **{"seamark:name": "Whittaker Creek Buoy 3"})
    pts = [PointObj("W", 1, "BOYLAT", "w", BX - 35 * DEG_PER_M, 0.01, dict(named), True),
           PointObj("E", 0, "BOYLAT", "e", BX + 40 * DEG_PER_M, 0.01, dict(named), True)]
    kept, dec = dedup.dedup(pts, TOL, 10, overlaps=ov)
    assert [(p.cell, p.lnam) for p in kept] == [("E", "e")] and dec[0].action == "merged"
    # beyond 2x tolerance: kept apart
    far = [PointObj("W", 1, "BOYLAT", "w", BX - 45 * DEG_PER_M, 0.01, dict(named), True),
           PointObj("E", 0, "BOYLAT", "e", BX + 60 * DEG_PER_M, 0.01, dict(named), True)]
    kept, _ = dedup.dedup(far, TOL, 10, overlaps=ov)
    assert len(kept) == 2
