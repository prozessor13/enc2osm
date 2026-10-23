import osmium
from osgeo import ogr

from enc2osm import writer
from enc2osm.pass2 import PointObj
from enc2osm.rejoin import Merged


def M(kind, wkt, **tags):
    g = ogr.CreateGeometryFromWkt(wkt)
    return Merged(kind, "X", bytes(g.ExportToWkb()), {"seamark:type": "t", **tags}, [])


def read(path):
    nodes, ways, rels = {}, {}, {}
    for o in osmium.FileProcessor(str(path)):
        if o.is_node():
            nodes[o.id] = (o.location.lon, o.location.lat, dict(o.tags))
        elif o.is_way():
            ways[o.id] = ([n.ref for n in o.nodes], dict(o.tags))
        else:
            rels[o.id] = ([(m.type, m.ref, m.role) for m in o.members], dict(o.tags))
    return nodes, ways, rels


def test_writer_structures(tmp_path):
    pts = [PointObj("C", 0, "BOYLAT", "a", 1.0, 1.0, {"seamark:type": "buoy_lateral"}),
           PointObj("C", 0, "LIGHTS", "b", 1.0, 1.0, {"seamark:type": "light_minor"})]
    long_line = "LINESTRING(" + ",".join(f"{i * 1e-5} 2" for i in range(4500)) + ")"
    shapes = [
        M("area", "MULTIPOLYGON(((0 0,1 0,1 1,0 0)))"),                       # simple -> way
        M("area", "MULTIPOLYGON(((0 0,3 0,3 3,0 3,0 0),(1 1,2 1,2 2,1 1)))"),  # hole -> relation
        M("line", "MULTILINESTRING((5 5,6 5,6 6,5 5))"),                      # closed line
        M("line", f"MULTI{long_line.replace('LINESTRING(', 'LINESTRING((')})"),
        M("line", "MULTILINESTRING((1 1,1.5 1.5))"),  # vertex at the buoy position
    ]
    out = tmp_path / "t.osm.pbf"
    st = writer.write(str(out), pts, shapes, "test", None)
    nodes, ways, rels = read(out)
    # two seamark nodes at identical coordinates stay separate, and a way vertex there too
    at11 = [nid for nid, (x, y, _) in nodes.items() if (x, y) == (1.0, 1.0)]
    assert len(at11) == 3 and st["seamark_nodes"] == 2
    tagged_ways = [w for w in ways.values() if w[1]]
    assert any(w[1].get("area") == "no" for w in tagged_ways)
    assert all(len(n) <= writer.MAX_WAY_NODES for n, _ in ways.values())
    long_parts = sorted((n for n, t in ways.values() if len(n) > 100), key=lambda n: n[0])
    assert [len(n) for n in long_parts] == [2000, 2000, 502]  # 4500 nodes, shared end nodes
    assert long_parts[0][-1] == long_parts[1][0] and long_parts[1][-1] == long_parts[2][0]
    assert len(rels) == 1
    members, tags = next(iter(rels.values()))
    assert tags["type"] == "multipolygon" and {r for _, _, r in members} == {"outer", "inner"}
    # Planetiler: node ids ascending and >= 1 in file order
    ids = [o.id for o in osmium.FileProcessor(str(out), osmium.osm.NODE)]
    assert ids == sorted(ids) and ids[0] == 1


def test_negative_ids(tmp_path):
    pts = [PointObj("C", 0, "BOYLAT", "a", 1.0, 1.0, {"seamark:type": "buoy_lateral"})]
    out = tmp_path / "n.osm.pbf"
    writer.write(str(out), pts, [M("line", "MULTILINESTRING((0 0,1 1))")], "t", None,
                 negative_ids=True)
    nodes, ways, _ = read(out)
    assert sorted(nodes) == [-3, -2, -1] and list(ways.values())[0][0] == [-2, -3]


def test_vertex_spill_gives_identical_file(tmp_path):
    pts = [PointObj("C", 0, "BOYLAT", "a", 1.0, 1.0, {"seamark:type": "buoy_lateral"})]
    shapes = [M("line", "MULTILINESTRING((" + ",".join(f"{i * 1e-4} {(i % 7) * 1e-4}"
                                                      for i in range(300)) + "))"),
              M("area", "MULTIPOLYGON(((0 0,0.01 0,0.01 0.01,0 0)))")]
    a, b = tmp_path / "a.osm.pbf", tmp_path / "b.osm.pbf"
    writer.write(str(a), pts, shapes, "t", None)
    st = writer.write(str(b), pts, shapes, "t", None, spill_at=10)
    assert a.read_bytes() == b.read_bytes() and st["vertex_nodes"] == 302
