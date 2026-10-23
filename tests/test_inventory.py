import shutil

from osgeo import ogr

from enc2osm import inventory


def _mem_covr(polys):
    ds = ogr.GetDriverByName("Memory").CreateDataSource("m")
    lyr = ds.CreateLayer("M_COVR", geom_type=ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("CATCOV", ogr.OFTInteger))
    for catcov, wkt in polys:
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("CATCOV", catcov)
        f.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
        lyr.CreateFeature(f)
    return ds


def test_coverage_union_and_nocov():
    ds = _mem_covr([
        (1, "POLYGON((0 0,1 0,1 1,0 1,0 0))"),
        (1, "POLYGON((1 0,2 0,2 1,1 1,1 0))"),
        (2, "POLYGON((0 0,0.5 0,0.5 0.5,0 0.5,0 0))"),
    ])
    cov = inventory.read_coverage(ds)
    assert abs(cov.GetArea() - 1.75) < 1e-9


def test_coverage_missing():
    assert inventory.read_coverage(_mem_covr([(2, "POLYGON((0 0,1 0,1 1,0 0))")])) is None
    ds = ogr.GetDriverByName("Memory").CreateDataSource("m")
    assert inventory.read_coverage(ds) is None


def test_small_inventory(small_dir):
    cells, skipped = inventory.build([str(small_dir)])
    assert not skipped
    assert len(cells) == 14
    assert sorted({c.band for c in cells}) == [1, 2, 3, 4, 5]
    fg = next(c for c in cells if c.name == "US5OAKFG")
    assert (fg.band, fg.edition, fg.update, fg.cscale) == (5, 1, 2, 12000)
    assert fg.coverage.GetArea() > 0


def test_duplicate_and_broken_cells(tmp_path, small_dir):
    a, b = tmp_path / "a", tmp_path / "b"
    shutil.copytree(small_dir / "US5OAKFG", a / "US5OAKFG")
    # second copy without the update files -> older update number -> loses
    (b / "US5OAKFG").mkdir(parents=True)
    shutil.copy(small_dir / "US5OAKFG" / "US5OAKFG.000", b / "US5OAKFG")
    (tmp_path / "BROKEN01.000").write_bytes(b"not an ENC")
    cells, skipped = inventory.build([str(tmp_path)])
    assert [(c.name, c.update) for c in cells] == [("US5OAKFG", 2)]
    assert str(a) in cells[0].path
    reasons = sorted(s.reason.split(" ")[0] for s in skipped)
    assert len(skipped) == 2 and "duplicate" in reasons
