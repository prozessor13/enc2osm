from collections import Counter
from pathlib import Path

import pytest
from golden_cases import CASES

from enc2osm import aggregate, extract, inventory, mapping, tags

ROOT = Path(__file__).resolve().parent.parent
M = mapping.load()
_cache: dict = {}


def objects_of(src: str, cell: str, scope: str = "v1") -> dict:
    key = (src, cell, scope)
    if key not in _cache:
        path = ROOT / src / cell / f"{cell}.000"
        if not path.exists():
            pytest.skip(f"missing fixture {path}")
        info = inventory.read_cell(path)
        st = Counter()
        fs = extract.read_features(info.path, M, M.classes(scope), info.duni, info.huni, st)
        _cache[key] = {a.lnam: tags.build(a, info, M, st)
                       for a in aggregate.aggregate(fs, M, st)}
    return _cache[key]


@pytest.mark.parametrize("case", CASES, ids=[f"{c['cell']}-{c['lnam']}" for c in CASES])
def test_golden(case):
    got = objects_of(case["src"], case["cell"], case.get("scope", "v1"))[case["lnam"]]
    seamark = {k: v for k, v in got.items() if k.startswith("seamark:")}
    assert seamark == case["tags"], case["raw"]
    assert got["enc:lnam"] == case["lnam"] and got["enc:cell"] == case["cell"]


def test_golden_count():
    assert sum(c.get("scope", "v1") == "v1" for c in CASES) >= 30
