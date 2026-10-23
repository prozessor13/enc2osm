from osgeo import ogr

from enc2osm import coverage, inventory
from enc2osm.inventory import CellInfo


def cell(name, band, wkt, cscale=10000, isdt="20260101"):
    g = ogr.CreateGeometryFromWkt(wkt)
    if ogr.GT_Flatten(g.GetGeometryType()) == ogr.wkbPolygon:
        g = ogr.ForceToMultiPolygon(g)
    minx, maxx, miny, maxy = g.GetEnvelope()
    return CellInfo(name, "", band, 1, 0, isdt, cscale, 1, 1, bytes(g.ExportToWkb()),
                    (minx, miny, maxx, maxy))


def box(x0, y0, x1, y1):
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def area(eff, name):
    return eff[name].geom.GetArea()


def test_priority_order():
    cs = [cell("A", 3, box(0, 0, 1, 1)), cell("B", 5, box(0, 0, 1, 1), cscale=20000),
          cell("C", 5, box(0, 0, 1, 1), cscale=10000, isdt="20250101"),
          cell("D", 5, box(0, 0, 1, 1), cscale=10000, isdt="20260101"),
          cell("E", 5, box(0, 0, 1, 1), cscale=10000, isdt="20260101")]
    assert [c.name for c in coverage.ordered(cs)] == ["D", "E", "C", "B", "A"]


def test_nested_harbour_cuts_out_approach():
    eff = coverage.resolve([cell("APP", 3, box(0, 0, 1, 1)),
                            cell("HBR", 5, box(0.25, 0.25, 0.5, 0.5))])
    assert abs(area(eff, "HBR") - 0.0625) < 1e-12
    assert abs(area(eff, "APP") - (1 - 0.0625)) < 1e-12
    assert eff["HBR"].rank == 0


def test_partial_overlap_and_same_band_tiebreak():
    eff = coverage.resolve([cell("X", 4, box(0, 0, 1, 1), cscale=40000),
                            cell("Y", 4, box(0.5, 0, 1.5, 1), cscale=20000)])
    # same band: larger scale (smaller CSCL) wins the overlap
    assert abs(area(eff, "Y") - 1.0) < 1e-12
    assert abs(area(eff, "X") - 0.5) < 1e-12


def test_same_band_same_scale_newer_wins_then_name():
    eff = coverage.resolve([cell("OLD", 5, box(0, 0, 1, 1), isdt="20200101"),
                            cell("NEW", 5, box(0.5, 0, 1.5, 1), isdt="20250101")])
    assert abs(area(eff, "NEW") - 1.0) < 1e-12
    eff = coverage.resolve([cell("B", 5, box(0, 0, 1, 1)), cell("A", 5, box(0.5, 0, 1.5, 1))])
    assert abs(area(eff, "A") - 1.0) < 1e-12 and abs(area(eff, "B") - 0.5) < 1e-12


def test_fully_shadowed_cell_is_empty():
    eff = coverage.resolve([cell("BIG5", 5, box(0, 0, 1, 1)),
                            cell("SMALL3", 3, box(0.2, 0.2, 0.4, 0.4))])
    assert eff["SMALL3"].geom.IsEmpty()


def test_slivers_dropped():
    # lower cell sticks out by 1e-8 deg (~1 mm) over ~1.1 km -> ~1.2 m² sliver
    eff = coverage.resolve([cell("HI", 5, box(0, 0, 0.01, 0.01)),
                            cell("LO", 4, box(0, 0, 0.01, 0.01000001))], sliver_m2=10)
    assert eff["LO"].geom.IsEmpty() and eff["LO"].slivers_dropped == 1


def invariants(cells, eff, tol=1e-9):
    covs = ogr.Geometry(ogr.wkbMultiPolygon)
    effs = ogr.Geometry(ogr.wkbMultiPolygon)
    total = 0.0
    for c in cells:
        for g, acc in ((c.coverage, covs), (eff[c.name].geom, effs)):
            for i in range(g.GetGeometryCount()):
                acc.AddGeometry(g.GetGeometryRef(i))
        total += eff[c.name].geom.GetArea()
    u_cov, u_eff = covs.UnionCascaded(), effs.UnionCascaded()
    # union equality (within sliver tolerance) and no overlap (sum of areas == area of union)
    assert u_cov.SymDifference(u_eff).GetArea() < tol * max(1.0, u_cov.GetArea()) + 1e-8
    assert abs(total - u_eff.GetArea()) < 1e-8


def test_fixture_invariants(small_dir):
    cells, _ = inventory.build([str(small_dir)])
    eff = coverage.resolve(cells)
    invariants(cells, eff)
    # harbour-scale cell keeps its whole coverage
    fg = next(c for c in cells if c.name == "US5OAKFG")
    assert abs(eff["US5OAKFG"].geom.GetArea() - fg.coverage.GetArea()) < 1e-10


def test_medium_invariants(medium_dir):
    cells, _ = inventory.build([str(medium_dir)])
    invariants(cells, coverage.resolve(cells))
