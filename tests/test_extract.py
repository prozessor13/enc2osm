from collections import Counter

from osgeo import ogr

from enc2osm import extract, inventory, mapping

M = mapping.load()


def test_unit_conversion():
    st = Counter()
    a = {"VALSOU": 10.0, "HEIGHT": 100.0, "COLOUR": ["1"]}
    assert extract.convert_units(a, M, 1, 1, st) == a
    assert extract.convert_units(a, M, 3, 2, st) == {"VALSOU": 3.05, "HEIGHT": 30.48,
                                                     "COLOUR": ["1"]}
    assert extract.convert_units(a, M, 4, 1, st)["VALSOU"] == 18.29
    # fathoms+feet encoding is not converted: attribute dropped and counted
    out = extract.convert_units(a, M, 2, 9, st)
    assert "VALSOU" not in out and "HEIGHT" not in out
    assert st["unit_unknown:VALSOU:DUNI=2"] == 1 and st["unit_unknown:HEIGHT:HUNI=9"] == 1


def _nsys(*items):
    return [(ogr.CreateGeometryFromWkt(w), m) for w, m in items]


def _pt(attrs=None):
    return extract.Feature("BOYLAT", "L", "point", b"", attrs or {}, [], 0.5, 0.5)


def test_marsys_inheritance():
    sq = "POLYGON((0 0,1 0,1 1,0 1,0 0))"
    st = Counter()
    f = _pt()
    extract.inherit_marsys(f, _nsys((sq, 2)), st)
    assert f.attrs["MARSYS"] == 2
    f = _pt({"MARSYS": 1})  # own value wins
    extract.inherit_marsys(f, _nsys((sq, 2)), st)
    assert f.attrs["MARSYS"] == 1
    f = _pt()  # conflicting areas -> unset
    extract.inherit_marsys(f, _nsys((sq, 1), (sq, 2)), st)
    assert "MARSYS" not in f.attrs and st["marsys_conflict"] == 1
    f = _pt()  # outside every area -> unset
    extract.inherit_marsys(f, _nsys(("POLYGON((5 5,6 5,6 6,5 5))", 2)), st)
    assert "MARSYS" not in f.attrs


def test_read_small_cell(small_dir):
    cells, _ = inventory.build([str(small_dir / "US5OAKFG")])
    c, st = cells[0], Counter()
    fs = extract.read_features(c.path, M, M.classes("v1"), c.duni, c.huni, st)
    assert st["read:LIGHTS"] == 39 and len(fs) == 277
    b = next(f for f in fs if f.lnam == "0226011CA73C0032")
    assert b.cls == "BCNLAT" and b.attrs["CATLAM"] == 1 and b.attrs["MARSYS"] == 2
    assert ("0226011CA73E0032", 2) in b.refs
    assert all(f.kind == "point" or f.cls in ("OBSTRN", "MORFAC", "WRECKS", "LNDMRK")
               for f in fs)
    lights = [f for f in fs if f.cls == "LIGHTS"]
    assert all("MARSYS" not in f.attrs for f in lights)
