"""End-to-end build on the small fixture (CLI path)."""
import json

import osmium

from enc2osm import cli

BBOX = (-122.48, 37.80, -122.40, 37.85)  # Alcatraz / North Channel


def _nodes(path):
    return [(n.location.lon, n.location.lat, dict(n.tags))
            for n in osmium.FileProcessor(str(path), osmium.osm.NODE) if "seamark:type" in n.tags]


def test_build_small_with_bbox(tmp_path, small_dir, capsys):
    out, rep = tmp_path / "s.osm.pbf", tmp_path / "rep"
    assert cli.main(["build", "-o", str(out), "--classes", "v2", "--report", str(rep),
                     "--bbox", ",".join(map(str, BBOX)), str(small_dir)]) == 0
    summary = json.loads(capsys.readouterr().out)
    nodes = _nodes(out)
    assert nodes and all(BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3] for x, y, _ in nodes)
    assert summary["points_written"] == len(nodes)
    for f in ("dedup.csv", "dropped_without_counterpart.csv", "stats.json",
              "stats_per_cell.json"):
        assert (rep / f).exists()
    names = {t.get("seamark:name") for _, _, t in nodes}
    assert {"Alcatraz Light", "Alcatraz Lighted Bell Buoy AZ"} <= names


def test_build_osm_xml_and_keep_raw(tmp_path, small_dir, capsys):
    out = tmp_path / "s.osm"
    assert cli.main(["build", "-o", str(out), "--keep-raw", str(small_dir / "US5OAKFG")]) == 0
    text = out.read_text()
    assert text.startswith("<?xml") and 'k="enc:QUASOU"' in text
