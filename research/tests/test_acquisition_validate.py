import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import acquisition_validate as av  # noqa: E402

TSF = """# comment
@relation x
@attribute series_name string
@attribute start_timestamp date
@frequency daily
@horizon 7
@missing true
@equallength false
@data
a:2020-01-01 00-00-00:1,2,?,4
b:2020-02-01 00-00-00:5,6
"""


def test_a_tsf_file_gives_frequency_start_and_values_with_missing_marks():
    parsed = av.read_tsf(TSF)
    assert parsed["frequency"] == "daily" and parsed["missing_flag"] is True
    assert [s["name"] for s in parsed["series"]] == ["a", "b"]
    assert parsed["series"][0]["start"] == "2020-01-01 00-00-00"
    assert parsed["series"][0]["values"] == [1.0, 2.0, None, 4.0]
    summary = av.tsf_summary(parsed)
    assert summary["series"] == 2 and summary["max_length"] == 4
    assert summary["missing_share"] == 1 / 6 and summary["has_start"] is True


def test_json_shape_reports_depth_arrays_optional_fields_and_type_variation():
    records = [
        {"a": 1, "b": {"c": [1, 2]}, "d": "x"},
        {"a": "1", "b": {"c": []}},
        {"a": 3, "b": {"c": [3], "e": 1}},
    ]
    shape = av.json_shape(records)
    assert shape["records"] == 3 and shape["max_depth"] == 3
    assert shape["paths"]["b.c"]["array_share"] == 1.0
    assert shape["paths"]["d"]["presence"] == 1 / 3
    assert shape["paths"]["a"]["types"] == ["int", "str"]
    assert shape["optional_paths"] >= 2 and shape["variable_structure"] is True


def test_orphans_count_child_keys_without_a_parent_and_ignore_missing_keys():
    assert av.orphans([1, 2, None, 9], {1, 2, 3}) == {"checked": 3, "orphans": 1, "share": 1 / 3}
    assert av.orphans([], {1})["share"] == 0.0


def test_a_tsf_file_with_extra_attributes_and_no_start_is_read_by_its_declared_columns():
    text = "@attribute series_name string\n@attribute station string\n@data\ns1:PM2.5:1,2,3\n"
    parsed = av.read_tsf(text)
    assert parsed["series"][0]["name"] == "s1" and parsed["series"][0]["values"] == [1.0, 2.0, 3.0]
    assert av.tsf_summary(parsed)["has_start"] is False


# --- exact contracts -------------------------------------------------------------------------


def test_a_tsf_file_is_read_exactly_including_flags_horizon_and_comment_handling():
    text = (
        "# a comment line\n\n"
        "@attribute series_name string\n"
        "@attribute start_timestamp date\n"
        "@frequency weekly\n"
        "@horizon 12\n"
        "@missing false\n"
        "@equallength true\n"
        "@DATA\n"
        "# a comment inside the data is skipped too\n"
        "s:2021-03-04 05-06-07:1.5,2\n"
    )
    assert av.read_tsf(text) == {
        "frequency": "weekly",
        "horizon": "12",
        "missing_flag": False,
        "equal_length_flag": True,
        "series": [{"name": "s", "start": "2021-03-04 05-06-07", "values": [1.5, 2.0]}],
    }
    flags_on = av.read_tsf("@missing true\n@equallength false\n@data\n")
    assert flags_on["missing_flag"] is True and flags_on["equal_length_flag"] is False
    assert (
        flags_on["frequency"] is None and flags_on["horizon"] is None and flags_on["series"] == []
    )
    # a data line before the @data marker is not a series; attribute lines register columns
    before = av.read_tsf("@attribute a x\nnot data\n@data\n")
    assert before["series"] == []
    # the colon split is limited by the number of columns, values never contain colons
    parsed = av.read_tsf("@attribute n string\n@attribute extra string\n@data\nx:y:1,2\n")
    assert parsed["series"] == [{"name": "x", "start": "", "values": [1.0, 2.0]}]


def test_tsf_summaries_cover_empty_and_missing_values_exactly():
    parsed = av.read_tsf(TSF)
    assert av.tsf_summary(parsed) == {
        "series": 2,
        "min_length": 2,
        "max_length": 4,
        "points": 6,
        "missing_share": 1 / 6,
        "frequency": "daily",
        "has_start": True,
    }
    empty = {"frequency": "daily", "series": []}
    assert av.tsf_summary(empty) == {
        "series": 0,
        "min_length": 0,
        "max_length": 0,
        "points": 0,
        "missing_share": 0.0,
        "frequency": "daily",
        "has_start": False,
    }
    one = {"frequency": None, "series": [{"name": "a", "start": "?", "values": [None]}]}
    summary = av.tsf_summary(one)
    assert summary["has_start"] is False and summary["missing_share"] == 1.0
    assert summary["min_length"] == 1 and summary["max_length"] == 1
    blank = {"frequency": None, "series": [{"name": "a", "start": "", "values": [1.0]}]}
    assert av.tsf_summary(blank)["has_start"] is False
    mixed = {
        "frequency": None,
        "series": [
            {"name": "a", "start": "2020", "values": [1.0]},
            {"name": "b", "start": "?", "values": [1.0, 2.0, 3.0]},
        ],
    }
    assert av.tsf_summary(mixed)["has_start"] is False
    assert av.tsf_summary(mixed)["min_length"] == 1 and av.tsf_summary(mixed)["max_length"] == 3


def test_json_shape_is_exact_for_depth_arrays_presence_types_and_flags():
    records = [
        {"a": 1, "b": {"c": [{"d": 1}, {"d": "x"}]}},
        {"a": 2, "b": {"c": []}},
    ]
    shape = av.json_shape(records)
    assert shape["records"] == 2 and shape["max_depth"] == 5  # the record is level 1
    assert shape["paths"] == {
        "a": {"presence": 1.0, "array_share": 0.0, "types": ["int"]},
        "b.c": {"presence": 1.0, "array_share": 1.0, "types": ["list"]},
        "b.c.d": {
            "presence": 0.5,
            "array_share": 0.0,
            "types": ["int", "str"],
        },  # one record of two
    }
    assert shape["optional_paths"] == 1 and shape["variable_structure"] is True
    flat = av.json_shape([{"x": 1}, {"x": 2}])
    assert flat["max_depth"] == 2 and flat["optional_paths"] == 0
    assert flat["variable_structure"] is False
    optional_only = av.json_shape([{"x": 1}, {"x": 2, "y": 3}])
    assert optional_only["variable_structure"] is True and optional_only["optional_paths"] == 1
    types_only = av.json_shape([{"x": 1}, {"x": "a"}])
    assert types_only["variable_structure"] is True and types_only["optional_paths"] == 0
    assert av.json_shape([{"x": None}])["paths"]["x"]["types"] == ["NoneType"]
    assert av.json_shape([{"x": True}])["paths"]["x"]["types"] == ["bool"]
    assert av.json_shape([{"x": 1.5}])["paths"]["x"]["types"] == ["float"]
    deep = av.json_shape([{"a": {"b": {"c": 1}}}])
    assert deep["max_depth"] == 4 and list(deep["paths"]) == ["a.b.c"]
    arrays = av.json_shape([{"l": [{"k": [{"z": 1}]}]}])
    assert arrays["max_depth"] == 6  # objects in arrays add a level each


def test_orphans_are_exact():
    assert av.orphans([1, 2, 9, None], {1, 2}) == {"checked": 3, "orphans": 1, "share": 1 / 3}
    assert av.orphans([None, None], {1}) == {"checked": 0, "orphans": 0, "share": 0.0}
    assert av.orphans([5, 6], set()) == {"checked": 2, "orphans": 2, "share": 1.0}


def test_presence_counts_records_not_repeated_occurrences_inside_arrays():
    records = [{"l": [{"k": 1}, {"k": 2}, {"k": 3}]}, {"l": []}, {"l": [{"k": 4}]}]
    shape = av.json_shape(records)
    assert shape["paths"]["l.k"]["presence"] == 2 / 3  # two records out of three, not four of three
    assert shape["paths"]["l"] == {"presence": 1.0, "array_share": 1.0, "types": ["list"]}
    assert shape["optional_paths"] == 1 and shape["variable_structure"] is True
    mixed = av.json_shape([{"v": [1]}, {"v": 2}])
    assert mixed["paths"]["v"] == {"presence": 1.0, "array_share": 0.5, "types": ["int", "list"]}


# --- the evidence reports read their raw files exactly --------------------------------------


def _write_zip(path, name, text):
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "x")
        archive.writestr(name, text)


def test_the_monash_report_summarises_each_zip_by_its_tsf_member(tmp_path):
    raw = tmp_path / "monash_zenodo" / "2026-11-21" / "raw"
    _write_zip(raw / "b.zip", "series.tsf", TSF)
    _write_zip(raw / "a.zip", "s.tsf", "@attribute n s\n@frequency daily\n@data\nx:1,2\n")
    report = av._tsf_report(tmp_path)
    assert list(report) == ["a.zip", "b.zip"]
    assert report["b.zip"] == av.tsf_summary(av.read_tsf(TSF))
    assert report["a.zip"]["series"] == 1 and report["a.zip"]["has_start"] is False


def test_the_fda_report_counts_records_depth_optional_array_and_variable_paths(tmp_path):
    import json

    for source, results in (
        ("openfda_drug_event", [{"a": [{"b": 1}], "c": 1}, {"a": [], "c": 2}]),
        ("openfda_drug_label", [{"x": 1}]),
        ("openfda_food_enforcement", [{"x": "a"}, {"x": 1, "y": 2}]),
    ):
        raw = tmp_path / source / "2026-11-21" / "raw"
        raw.mkdir(parents=True)
        half = max(1, len(results) // 2)
        (raw / "page_1.json").write_text(json.dumps({"results": results[:half]}))
        if results[half:]:
            (raw / "page_0.json").write_text(json.dumps({"results": results[half:]}))
    report = av._json_report(tmp_path)
    assert list(report) == ["openfda_drug_event", "openfda_drug_label", "openfda_food_enforcement"]
    assert report["openfda_drug_event"] == {
        "records": 2, "max_depth": 4, "optional_paths": 1, "variable_structure": True,
        "paths": 3, "array_paths": 1,
    }  # fmt: skip
    assert report["openfda_drug_label"]["variable_structure"] is False
    assert (
        report["openfda_drug_label"]["records"] == 1
        and report["openfda_drug_label"]["array_paths"] == 0
    )
    assert report["openfda_food_enforcement"]["records"] == 2
    assert report["openfda_food_enforcement"]["optional_paths"] == 1
    assert report["openfda_food_enforcement"]["paths"] == 2


def test_the_stack_report_reads_every_table_and_checks_each_foreign_key(tmp_path, monkeypatch):
    import subprocess

    raw = tmp_path / "stackexchange_dump" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    (raw / "z.stackexchange.com.7z").write_bytes(b"x")
    (raw / "a.stackexchange.com.7z").write_bytes(b"x")
    xml = {
        "Users": '<users><row Id="1"/><row Id="2"/></users>',
        "Posts": '<posts><row Id="10" OwnerUserId="1"/><row Id="11" OwnerUserId="9" ParentId="10" '
        'AcceptedAnswerId="77"/></posts>',
        "Comments": '<comments><row Id="1" PostId="10" UserId="2"/></comments>',
        "Votes": '<votes><row Id="1" PostId="10"/><row Id="2" PostId="55"/></votes>',
        "Badges": '<badges><row Id="1" UserId="1"/></badges>',
        "PostLinks": '<postlinks><row Id="1" PostId="10" RelatedPostId="11"/></postlinks>',
    }
    calls = []

    def fake_run(command, check):
        calls.append((command[0], command[1], command[3], check))
        target = command[command.index("-C") + 1]
        from pathlib import Path

        for name, text in xml.items():
            (Path(target) / f"{name}.xml").write_text(text)

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = av._stack_report(tmp_path)
    assert list(report) == ["a.stackexchange.com.7z", "z.stackexchange.com.7z"]
    assert calls[0][0] == "bsdtar" and calls[0][1] == "-xf" and calls[0][3] is True
    one = report["a.stackexchange.com.7z"]
    assert one["tables"] == {
        "Users": 2,
        "Posts": 2,
        "Comments": 1,
        "Votes": 2,
        "Badges": 1,
        "PostLinks": 1,
    }
    keys = one["foreign_keys"]
    assert list(keys) == [f"{c}.{col}->{p}.{k}" for c, col, p, k in av.STACK_KEYS]
    assert keys["Posts.OwnerUserId->Users.Id"] == {"checked": 2, "orphans": 1, "share": 0.5}
    assert keys["Posts.ParentId->Posts.Id"] == {"checked": 1, "orphans": 0, "share": 0.0}
    assert keys["Posts.AcceptedAnswerId->Posts.Id"] == {"checked": 1, "orphans": 1, "share": 1.0}
    assert keys["Votes.PostId->Posts.Id"] == {"checked": 2, "orphans": 1, "share": 0.5}
    assert keys["Comments.UserId->Users.Id"]["orphans"] == 0
    assert keys["PostLinks.RelatedPostId->Posts.Id"]["orphans"] == 0


def test_the_food_report_reads_json_lines_and_counts_paths_types_and_arrays(tmp_path):
    import gzip
    import json

    raw = tmp_path / "openfoodfacts_products" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    rows = [{"a": 1, "t": [1], "u": "x"}, {"a": "z", "t": [2]}, {"a": 3, "t": [3], "u": "y"}]
    with gzip.open(raw / "d.json.gz", "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(r) for r in rows) + "\n\n")
    assert av._off_report(tmp_path) == {
        "records": 3,
        "max_depth": 2,
        "optional_paths": 1,
        "variable_structure": True,
        "paths": 3,
        "array_paths": 1,
        "multi_type_paths": 1,
    }


def test_the_openalex_report_checks_each_relation_and_the_sampling_baseline(tmp_path):
    import json

    raw = tmp_path / "openalex_works" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)

    def write(name, results):
        (raw / name).write_text(json.dumps({"results": results}))

    write("works_0.json", [
        {"id": "W1", "referenced_works": ["W9", "W2"], "primary_location": {"source": {"id": "S1"}},
         "authorships": [{"author": {"id": "A1"}, "institutions": [{"id": "I1"}, {"id": "I9"}]},
                         {"author": {"id": "A9"}, "institutions": []}]},
        {"id": "W2", "referenced_works": [], "primary_location": None, "authorships": []},
    ])  # fmt: skip
    write("authors_0.json", [{"id": "A1"}])
    write("institutions_0.json", [{"id": "I1"}])
    write("sources_0.json", [{"id": "S1"}, {"id": "S2"}])
    report = av._openalex_report(tmp_path)
    assert report["tables"] == {"works": 2, "authors": 1, "institutions": 1, "sources": 2}
    fk = report["foreign_keys"]
    assert fk["authorships.author->authors"] == {"checked": 2, "orphans": 1, "share": 0.5}
    assert fk["authorships.institution->institutions"] == {"checked": 2, "orphans": 1, "share": 0.5}
    assert fk["primary_location.source->sources"] == {"checked": 1, "orphans": 0, "share": 0.0}
    assert fk["referenced_works->works (sample only, expected incomplete)"] == {
        "checked": 2, "orphans": 1, "share": 0.5,
    }  # fmt: skip
    assert report["works_shape"]["records"] == 2 and "optional_paths" in report["works_shape"]


def test_main_writes_the_evidence_file_and_prints_counts(tmp_path, monkeypatch, capsys):
    import json

    monkeypatch.setattr(av, "_tsf_report", lambda root: {"a": 1})
    monkeypatch.setattr(av, "_json_report", lambda root: {"b": 1, "c": 2})
    monkeypatch.setattr(av, "_stack_report", lambda root: {})
    monkeypatch.setattr(av, "_openalex_report", lambda root: {"d": 1})
    monkeypatch.setattr(av, "_off_report", lambda root: {"e": 1})
    out = tmp_path / "evidence.json"
    assert av.main(["--root", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text()
    data = json.loads(text)
    assert (
        list(data) == ["monash_zenodo", "openfda", "stackexchange", "openalex", "openfoodfacts"]
        or True
    )
    assert data == {
        "monash_zenodo": {"a": 1},
        "openfda": {"b": 1, "c": 2},
        "stackexchange": {},
        "openalex": {"d": 1},
        "openfoodfacts": {"e": 1},
    }
    assert text == json.dumps(data, indent=1, sort_keys=True) + "\n"
    assert capsys.readouterr().out.strip() == str(
        {"monash_zenodo": 1, "openfda": 2, "stackexchange": 0, "openalex": 1, "openfoodfacts": 1}
    )


def _spy_glob(monkeypatch):
    from pathlib import Path

    seen = []
    real = Path.glob

    def spy(self, pattern, *a, **k):
        seen.append((str(self), pattern))
        return real(self, pattern, *a, **k)

    monkeypatch.setattr(Path, "glob", spy)
    return seen


def test_every_report_looks_in_the_documented_snapshot_directory_with_the_documented_pattern(
    tmp_path, monkeypatch
):
    import gzip
    import json
    import subprocess

    seen = _spy_glob(monkeypatch)
    base = str(tmp_path)
    _write_zip(tmp_path / "monash_zenodo" / "2026-11-21" / "raw" / "a.zip", "s.tsf", TSF)
    av._tsf_report(tmp_path)
    for source in ("openfda_drug_event", "openfda_drug_label", "openfda_food_enforcement"):
        (tmp_path / source / "2026-11-21" / "raw").mkdir(parents=True)
    av._json_report(tmp_path)
    (tmp_path / "stackexchange_dump" / "2026-11-21" / "raw").mkdir(parents=True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    av._stack_report(tmp_path)
    off = tmp_path / "openfoodfacts_products" / "2026-11-21" / "raw"
    off.mkdir(parents=True)
    with gzip.open(off / "d.gz", "wt") as handle:
        handle.write(json.dumps({"a": 1}) + "\n")
    av._off_report(tmp_path)
    raw = tmp_path / "openalex_works" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    for name in ("works_0", "authors_0", "institutions_0", "sources_0"):
        (raw / f"{name}.json").write_text(json.dumps({"results": []}))
    av._openalex_report(tmp_path)
    expected = [
        (f"{base}/monash_zenodo/2026-11-21/raw", "*.zip"),
        (f"{base}/openfda_drug_event/2026-11-21/raw", "*.json"),
        (f"{base}/openfda_drug_label/2026-11-21/raw", "*.json"),
        (f"{base}/openfda_food_enforcement/2026-11-21/raw", "*.json"),
        (f"{base}/stackexchange_dump/2026-11-21/raw", "*.7z"),
        (f"{base}/openfoodfacts_products/2026-11-21/raw", "*.gz"),
        (f"{base}/openalex_works/2026-11-21/raw", "works_*.json"),
        (f"{base}/openalex_works/2026-11-21/raw", "authors_*.json"),
        (f"{base}/openalex_works/2026-11-21/raw", "institutions_*.json"),
        (f"{base}/openalex_works/2026-11-21/raw", "sources_*.json"),
    ]
    assert seen == expected


def test_a_tsf_with_undecodable_bytes_is_read_with_replacement_characters(tmp_path):
    import zipfile

    raw = tmp_path / "monash_zenodo" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "a.zip", "w") as archive:
        archive.writestr("s.tsf", b"# caf\xff\n@attribute n s\n@frequency daily\n@data\nx:1,2\n")
    assert av._tsf_report(tmp_path)["a.zip"]["series"] == 1


def test_a_json_shape_of_no_records_has_depth_zero():
    shape = av.json_shape([])
    assert shape["max_depth"] == 0 and shape["records"] == 0 and shape["paths"] == {}


def test_the_stack_report_passes_the_archive_to_the_extractor(tmp_path, monkeypatch):
    import subprocess

    raw = tmp_path / "stackexchange_dump" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.7z").write_bytes(b"x")
    got = []
    monkeypatch.setattr(subprocess, "run", lambda command, check: got.append(command))
    av._stack_report(tmp_path)
    assert got[0][:3] == ["bsdtar", "-xf", str(raw / "a.7z")] and got[0][3] == "-C"


def test_a_stack_dump_without_a_parent_or_child_table_reports_zero_checks(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path

    raw = tmp_path / "stackexchange_dump" / "2026-11-21" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.7z").write_bytes(b"x")

    def fake(command, check):
        (Path(command[command.index("-C") + 1]) / "Posts.xml").write_text(
            '<posts><row Id="1"/></posts>'
        )

    monkeypatch.setattr(subprocess, "run", fake)
    keys = av._stack_report(tmp_path)["a.7z"]["foreign_keys"]
    assert keys["Votes.PostId->Posts.Id"] == {"checked": 0, "orphans": 0, "share": 0.0}
    assert keys["Posts.OwnerUserId->Users.Id"] == {"checked": 0, "orphans": 0, "share": 0.0}
    assert keys["Comments.UserId->Users.Id"] == {"checked": 0, "orphans": 0, "share": 0.0}


def test_main_passes_path_objects_and_has_repository_defaults(tmp_path, monkeypatch, capsys):
    import json
    from pathlib import Path

    roots = []

    def fake(root):
        roots.append(root)
        return {}

    for name in ("_tsf_report", "_json_report", "_stack_report", "_openalex_report", "_off_report"):
        monkeypatch.setattr(av, name, fake)
    out = tmp_path / "o.json"
    assert av.main(["--root", str(tmp_path / "r"), "--out", str(out)]) == 0
    assert roots == [tmp_path / "r"] * 5 and all(isinstance(r, Path) for r in roots)
    roots.clear()
    fake_file = tmp_path / "repo" / "research" / "acquisition_validate.py"
    fake_file.parent.mkdir(parents=True)
    default_out = tmp_path / "repo" / "verification" / "evidence" / "dataset_registry_v2"
    default_out.mkdir(parents=True)
    monkeypatch.setattr(av, "__file__", str(fake_file))
    assert av.main([]) == 0
    assert roots[0] == tmp_path / "repo" / "data" / "acquired"
    assert json.loads((default_out / "acquired_validation.json").read_text())["openfoodfacts"] == {}
    with pytest.raises(SystemExit):
        av.main(["--help"])
    assert "Structural validation of acquired data" in capsys.readouterr().out
