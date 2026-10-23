from enc2osm import cli, lnamcheck, s57


def test_discover_files_and_dirs(tmp_path, small_dir):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "X1234567.000").write_bytes(b"")
    (tmp_path / "a" / "X1234567.001").write_bytes(b"")
    (tmp_path / "b.txt").write_text("")
    found = s57.discover([str(tmp_path), str(tmp_path / "a" / "X1234567.000")])
    assert [p.name for p in found] == ["X1234567.000"]
    cells = s57.discover([str(small_dir)])
    assert len(cells) == 14 and all(p.suffix == ".000" for p in cells)


def test_lnam_summary_counts_multi_cell():
    seen = {c: {} for c in lnamcheck.CLASSES}
    seen["BOYLAT"] = {"A": {"C1", "C2"}, "B": {"C1"}}
    res = lnamcheck.summarize(seen)
    assert res["BOYLAT"] == {"lnams": 2, "in_multiple_cells": 1, "example": [["C1", "C2"]]}
    assert res["_total"]["share"] == 0.5


def test_lnam_check_runs_on_small(small_dir, capsys):
    assert cli.main(["lnam-check", "--json", str(small_dir)]) == 0
    assert '"_total"' in capsys.readouterr().out
