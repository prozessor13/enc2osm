"""On-disk temp store (stdlib sqlite3) for lines/areas, merged shapes and planned ways.

Keeps pass-2 line/area output, the re-join result and the writer's way list out of memory, so the
finalize step scales with the number of features per tag group, not with the whole dataset.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from array import array

from enc2osm.pass2 import ShapeObj


def _tags(t: dict) -> str:
    return json.dumps(t, sort_keys=True, separators=(",", ":"))


def identity_key(tags: dict) -> str:
    return _tags({k: v for k, v in tags.items() if not k.startswith("enc:")})


class TempStore:
    def __init__(self, directory: str | None = None):
        self._dir = tempfile.TemporaryDirectory(prefix="enc2osm-", dir=directory)
        self.db = sqlite3.connect(os.path.join(self._dir.name, "store.sqlite"))
        self.db.executescript("""
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            CREATE TABLE shapes(kind TEXT, ident TEXT, cell TEXT, rank INT, cls TEXT, lnam TEXT,
                                wkb BLOB, tags TEXT);
            CREATE TABLE merged(sortkey TEXT, kind TEXT, cls TEXT, wkb BLOB, tags TEXT);
            CREATE TABLE ways(id INTEGER PRIMARY KEY, nodes BLOB, tags TEXT);
            CREATE TABLE rels(id INTEGER PRIMARY KEY, members TEXT, tags TEXT);
        """)

    # -- pass 2 output ---------------------------------------------------------------------------
    def add_shapes(self, shapes: list[ShapeObj]) -> None:
        self.db.executemany(
            "INSERT INTO shapes VALUES (?,?,?,?,?,?,?,?)",
            [(s.kind, identity_key(s.tags), s.cell, s.rank, s.cls, s.lnam, s.wkb, _tags(s.tags))
             for s in shapes])

    def count_shapes(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM shapes").fetchone()[0]

    def groups(self):
        """Yield (kind, [ShapeObj...]) per identical (kind, tags-without-enc), deterministic."""
        cur = self.db.execute(
            "SELECT kind, ident, cell, rank, cls, lnam, wkb, tags FROM shapes "
            "ORDER BY kind, ident, cell, cls, lnam, wkb")
        key, items = None, []
        for kind, ident, cell, rank, cls, lnam, wkb, tags in cur:
            if (kind, ident) != key and items:
                yield key[0], items
                items = []
            key = (kind, ident)
            items.append(ShapeObj(cell, rank, cls, lnam, kind, wkb, json.loads(tags)))
        if items:
            yield key[0], items

    # -- re-join output --------------------------------------------------------------------------
    def add_merged(self, sortkey: tuple, kind: str, cls: str, wkb: bytes, tags: dict) -> None:
        self.db.execute("INSERT INTO merged VALUES (?,?,?,?,?)",
                        (json.dumps(sortkey), kind, cls, wkb, _tags(tags)))

    def merged(self):
        for _sk, kind, cls, wkb, tags in self.db.execute(
                "SELECT sortkey, kind, cls, wkb, tags FROM merged ORDER BY sortkey, wkb"):
            yield kind, cls, wkb, json.loads(tags)

    def count_merged(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM merged").fetchone()[0]

    # -- writer plan -----------------------------------------------------------------------------
    def add_way(self, wid: int, nodes: list[int], tags: dict) -> None:
        self.db.execute("INSERT INTO ways VALUES (?,?,?)",
                        (wid, array("q", nodes).tobytes(), _tags(tags)))

    def ways(self):
        for wid, nodes, tags in self.db.execute("SELECT id, nodes, tags FROM ways ORDER BY id"):
            a = array("q")
            a.frombytes(nodes)
            yield wid, a.tolist(), json.loads(tags)

    def add_rel(self, rid: int, members: list, tags: dict) -> None:
        self.db.execute("INSERT INTO rels VALUES (?,?,?)", (rid, json.dumps(members), _tags(tags)))

    def rels(self):
        for rid, members, tags in self.db.execute("SELECT id, members, tags FROM rels ORDER BY id"):
            yield rid, [tuple(m) for m in json.loads(members)], json.loads(tags)

    def close(self) -> None:
        self.db.close()
        self._dir.cleanup()
