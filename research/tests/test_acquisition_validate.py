import sys
from pathlib import Path

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
