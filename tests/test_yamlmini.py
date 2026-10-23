from pathlib import Path

import pytest

from enc2osm import yamlmini
from enc2osm.mapping import HERE


def test_subset():
    doc = """
# comment
A:
  1: white   # trailing comment
  2: "cone, point up"
  3: 'x # y'
B: {type: buoy, geometry: [point, area], n: 3, f: 1.5, t: true, z: null}
C: [a, b]
D:
E:
  nested:
    k: v
"""
    assert yamlmini.loads(doc) == {
        "A": {1: "white", 2: "cone, point up", 3: "x # y"},
        "B": {"type": "buoy", "geometry": ["point", "area"], "n": 3, "f": 1.5, "t": True,
              "z": None},
        "C": ["a", "b"], "D": None, "E": {"nested": {"k": "v"}},
    }


@pytest.mark.parametrize("bad", ["A: &x 1", "A: {a: {b: 1}}", "- item", "A: 1\nA: 2",
                                 "A: [1, [2]]", "\tA: 1"])
def test_rejects_outside_subset(bad):
    with pytest.raises(ValueError):
        yamlmini.loads(bad)


@pytest.mark.parametrize("name", ["objects.yaml", "attributes.yaml", "values.yaml", "rules.yaml"])
def test_matches_pyyaml(name):
    yaml = pytest.importorskip("yaml")
    text = Path(HERE / name).read_text()
    assert yamlmini.loads(text) == yaml.safe_load(text)
