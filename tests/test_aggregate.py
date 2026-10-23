from collections import Counter

from enc2osm import aggregate, mapping
from enc2osm.extract import Feature

M = mapping.load()


def F(cls, lnam, x=0.0, y=0.0, refs=(), kind="point", **attrs):
    return Feature(cls, lnam, kind, b"", attrs, list(refs), x, y)


def run(*fs):
    st = Counter()
    return {a.lnam: a for a in aggregate.aggregate(list(fs), M, st)}, st


def test_lnam_refs_and_reverse_refs():
    ags, st = run(F("BOYLAT", "B1", refs=[("L1", 2), ("T1", 2)]), F("LIGHTS", "L1"),
                  F("TOPMAR", "T1"), F("FOGSIG", "S1", refs=[("B1", 1)]))
    assert list(ags) == ["B1"]
    assert [s.lnam for s in ags["B1"].slaves] == ["L1", "S1", "T1"]  # light, fog, topmark
    assert st["slave_attached_lnam"] == 3


def test_position_fallback_unique_only():
    ags, st = run(F("BCNLAT", "B1", 1, 1), F("LIGHTS", "L1", 1, 1), F("LIGHTS", "L2", 2, 2))
    assert [s.lnam for s in ags["B1"].slaves] == ["L1"]
    assert ags["L2"].master is None and ags["L2"].standalone_cls == "LIGHTS"
    # two structures at the same spot: no guessing, the light stays standalone
    ags, st = run(F("BCNLAT", "B1", 1, 1), F("PILPNT", "P1", 1, 1), F("LIGHTS", "L1", 1, 1))
    assert ags["B1"].slaves == [] and ags["P1"].slaves == []
    assert ags["L1"].master is None and st["slave_position_ambiguous"] == 1


def test_standalone_lights_grouped_per_position_and_ordered():
    ags, st = run(F("LIGHTS", "L3", 5, 5, SECTR1=120.0, COLOUR=["3"]),
                  F("LIGHTS", "L1", 5, 5, SECTR1=10.0, COLOUR=["1"]),
                  F("LIGHTS", "L2", 5, 5, COLOUR=["1"]),
                  F("FOGSIG", "F1", 5, 5), F("LIGHTS", "X", 6, 6))
    grp = next(a for a in ags.values() if a.master is None and len(a.slaves) > 1)
    assert [s.lnam for s in grp.slaves] == ["L2", "L1", "L3", "F1"]
    assert grp.standalone_cls == "LIGHTS" and st["standalone_objects"] == 2


def test_slave_of_area_master_becomes_standalone():
    ags, st = run(F("LNDMRK", "M1", kind="area", refs=[("L1", 2)]), F("LIGHTS", "L1", 3, 3))
    assert ags["M1"].slaves == [] and ags["L1"].master is None
    assert st["slave_of_nonpoint_master"] == 1 and st["slave_attached_lnam"] == 0


def test_unresolved_refs_counted():
    _, st = run(F("BCNSPP", "B1", refs=[("RDO1", 2)]))
    assert st["ref_unresolved"] == 1


def test_light_numbering_order():
    ls = [F("LIGHTS", "a", SECTR1=200.0, COLOUR=["4"]), F("LIGHTS", "b", SECTR1=200.0,
          COLOUR=["3"]), F("LIGHTS", "c", COLOUR=["1"]), F("LIGHTS", "d", SECTR1=15.0)]
    assert [f.lnam for f in sorted(ls, key=aggregate.light_sort_key)] == ["c", "d", "b", "a"]
