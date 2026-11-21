"""Contracts of view helpers the file-level golden tests do not reach: types, limits, edge rows."""

import gzip
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import acquisition as aq  # noqa: E402
import experimental_views as ev  # noqa: E402
import parquet_reader as pr  # noqa: E402
import test_experimental_views as tev  # noqa: E402

SNAP = tev.SNAP


def test_dvf_values_that_are_not_numbers_become_missing_and_codes_keep_their_leading_zeros(
    tmp_path,
):
    raw = tev._dvf_frame().copy()
    raw.loc[
        0,
        ["valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales", "surface_terrain"],
    ] = "n/a"
    out = ev.dvf_view(raw)
    row = out[out["mutation"] == ev.pseudonym("2024-2")].iloc[0]
    assert (
        pd.isna(row["value_eur"])
        and pd.isna(row["built_area_m2"])
        and pd.isna(row["rooms"])
        and pd.isna(row["land_area_m2"])
    )
    root = tmp_path / "acquired"
    folder = root / "dgfip_dvf" / SNAP / "raw"
    folder.mkdir(parents=True)
    frame = tev._dvf_frame().assign(code_commune=["01076", "01076", "01076", "69381"])
    (folder / "dvf_69_2024.csv.gz").write_bytes(gzip.compress(frame.to_csv(index=False).encode()))
    ev._build_dvf(root, tmp_path / "o", {})
    assert (
        pd.read_csv(tmp_path / "o" / "dgfip_dvf" / "sales.csv", dtype=str)["commune"]
        .tolist()
        .count("01076")
        == 3
    )


def test_panel_and_event_csv_readers_keep_text_codes_and_the_declared_separator(tmp_path):
    root = tmp_path / "acquired"
    raw = root / "src" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "p.tsv").write_text("date\tkey\tn\n2020-01-01\t007\t3\n2020-01-02\t007\t4\n")
    manifest: dict = {}
    spec = {
        "s": {
            "source": "src",
            "file": "p.tsv",
            "sep": "\t",
            "time": ["date"],
            "format": "%Y-%m-%d",
            "keys": ["key"],
        }
    }
    import experimental_views as module

    original = module.PANEL_SPECS
    module.PANEL_SPECS = spec
    try:
        module._build_panels(root, tmp_path / "o", manifest)
    finally:
        module.PANEL_SPECS = original
    assert (tmp_path / "o" / "panels" / "s.csv").read_text().splitlines()[
        1
    ] == "2020-01-01,007,3"  # key stays text
    (raw / "e.csv").write_text("case;act;when;num;who\nA;007;01-02-2020 10:00:00;1;r\n")
    module.CSV_EVENT_SPECS, saved = {"src": {"file": "e.csv", "sep": ";", "case": "case", "activity": "act", "time": "when",  # noqa: E501
                                              "format": "%d-%m-%Y %H:%M:%S", "order": "num", "resource": "who", "modulo": 1}}, module.CSV_EVENT_SPECS  # fmt: skip  # noqa: E501
    try:
        module._build_csv_events(root, tmp_path / "o", {})
    finally:
        module.CSV_EVENT_SPECS = saved
    assert (tmp_path / "o" / "src" / "events.csv").read_text().splitlines()[1].split(",")[
        3
    ] == "007"


def test_header_less_prefix_keeps_literal_na_text_and_the_price_view_slices_dates_and_postcodes():
    frame, _ = ev.csv_prefix_no_header(
        b'"{A}","1000","2024-01-02 00:00","AB1 2CD","D","N","F","1","","S","","T","D","NA","A","A"\n'  # noqa: E501
    )
    assert (
        frame.iloc[0, 13] == "NA" and frame.iloc[0, 1] == "1000"
    )  # no NaN conversion, text columns
    out = ev.price_paid_view(frame)
    assert (
        out["county"].iloc[0] == "NA"
        and out["date"].iloc[0] == "2024-01-02"
        and out["postcode_district"].iloc[0] == "AB1"
    )
    odd = frame.copy()
    odd.iloc[0, 3] = "AB1  2CD"
    assert ev.price_paid_view(odd)["postcode_district"].iloc[0] == "AB1"


def test_a_byte_order_mark_is_removed_from_column_names_and_hours_are_added_to_dates():
    raw = pd.DataFrame({"﻿Date": ["2020-01-01"], "Hour": [5], "v": [1.0]})
    frame, stamps, used = ev._stamped(raw, {"time": ["Date"], "format": "%Y-%m-%d", "hour": "Hour"})
    assert (
        "Date" in frame.columns
        and stamps.iloc[0] == pd.Timestamp("2020-01-01 05:00:00")
        and used == {"Date", "Hour"}
    )
    _, _, plain = ev._stamped(raw, {"time": ["Date"], "format": "%Y-%m-%d"})
    assert plain == {"Date"}  # without an hour column only the time columns are used


def test_a_blank_key_is_not_a_known_parent_value_and_a_relation_without_values_has_zero_share():
    tables = {
        "a": pd.DataFrame({"k": ["x"]}),
        "b": pd.DataFrame({"k": ["", "x"]}),
        "c": pd.DataFrame({"k": [None, ""]}),
    }
    spec = {
        "tables": {n: {"keep": ["k"]} for n in tables},
        "relations": [["c", "k", "b", "k"], ["b", "k", "a", "k"]],
    }
    _, relations = ev.tables_view(tables, spec)
    assert relations[0] == {
        "child": "c.k",
        "parent": "b.k",
        "checked": 0,
        "orphans": 0,
        "share": 0.0,
    }
    assert (
        relations[1]["checked"] == 1 and relations[1]["orphans"] == 0
    )  # the blank is missing, not dangling
    only_blank_parent = ev.tables_view({"a": pd.DataFrame({"k": [""]}), "b": pd.DataFrame({"k": ["z"]})},  # noqa: E501
                                       {"tables": {"a": {"keep": ["k"]}, "b": {"keep": ["k"]}}, "relations": [["b", "k", "a", "k"]]})[1]  # fmt: skip  # noqa: E501
    assert only_blank_parent[0]["orphans"] == 1  # a blank parent key does not match


def test_open_library_view_counts_every_bad_line_and_keeps_reading_after_one():
    good = tev._ol_line(1)
    out, skipped = ev.open_library_view(
        [good, "bad", "a\tb", good.replace("/books/OL1M", "/books/OL2M"), "x\t1\t2\t3\tnot json"],
        modulo=1,
    )
    assert skipped == 3 and [r["key"] for r in out] == ["/books/OL1M", "/books/OL2M"]
    with pytest.raises(KeyError):
        ev.open_library_view(['/type/edition\tk\t1\t2\t{"no_key": 1}'], modulo=1)


def test_xes_view_selects_cases_by_hash_with_the_given_modulo_and_coerces_unreadable_numbers():
    traces = [{"case": f"c{i}", "attributes": {}, "events": [{"concept:name": "A", "time:timestamp": "2020-01-01T00:00:00Z", "n": "abc" if i == 0 else i}]} for i in range(12)]  # fmt: skip  # noqa: E501
    import hashlib

    kept = ev.xes_view(traces, modulo=3, numeric=["n"])
    want = sorted(
        f"c{i}" for i in range(12) if int(hashlib.sha256(f"c{i}".encode()).hexdigest(), 16) % 3 == 0
    )
    assert sorted(kept["case_id"].unique().tolist()) == want and 0 < len(want) < 12
    everything = ev.xes_view(traces, modulo=1, numeric=["n"])
    assert len(everything) == 12 and pd.isna(
        everything.loc[everything["case_id"] == "c0", "n"].iloc[0]
    )
    assert str(everything["n"].dtype) == "float64"


def test_surf_builder_picks_a_one_row_part_and_reports_when_every_part_is_empty(tmp_path):
    def archive(root, parts):
        raw = root / "zen_surf_lisa_slurm" / SNAP / "raw"
        raw.mkdir(parents=True)
        with zipfile.ZipFile(raw / "slurm_table_cleaned.zip", "w") as z:
            for name, frame in parts.items():
                path = tmp_path / f"{name}.parquet"
                pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)
                z.write(path, f"slurm_table_cleaned.parquet/{name}.snappy.parquet")

    one = tmp_path / "one"
    archive(one, {"part-00001-x": tev._surf_frame().iloc[:1]})
    manifest: dict = {}
    ev._build_surf(one, tmp_path / "o1", manifest)
    assert (
        manifest["zen_surf_lisa_slurm"]["files"]["jobs.csv"]["rows"] == 1
    )  # a single row is a valid part
    empty = tmp_path / "empty"
    archive(empty, {"part-00001-x": tev._surf_frame().iloc[:0]})
    with pytest.raises(ev.ViewError) as error:
        ev._build_surf(empty, tmp_path / "o2", {})
    assert str(error.value) == "no non-empty Parquet part in the archive"
    view = ev.surf_slurm_view(tev._surf_frame().assign(numcores=["16", "x", "8"]))
    assert str(view["job_id"].dtype) == "int64" and view["cores"].isna().sum() == 1


def test_builders_pass_their_documented_size_limits_to_the_readers(tmp_path, monkeypatch):
    seen = {}
    real_read, real_extract, real_gzip = pr.read_sample, aq.extract_member, aq.gzip_prefix_lines

    def read_spy(*args, **kwargs):
        seen.setdefault("read", []).append({k: kwargs[k] for k in ("max_rows",) if k in kwargs})
        return real_read(*args, **kwargs)

    def extract_spy(path, member, destination, max_bytes, max_ratio):
        seen.setdefault("extract", []).append((max_bytes, max_ratio))
        return real_extract(path, member, destination, max_bytes, max_ratio)

    def gzip_spy(blob, max_output):
        seen.setdefault("gzip", []).append(max_output)
        return real_gzip(blob, max_output)

    monkeypatch.setattr(pr, "read_sample", read_spy)
    monkeypatch.setattr(aq, "extract_member", extract_spy)
    monkeypatch.setattr(aq, "gzip_prefix_lines", gzip_spy)
    import test_view_builders as tvb

    for name in ("surf", "fugaku", "aegis", "borg", "openlibrary"):
        setup, builder, _, patches = tvb.CASES[name]
        root, out = tmp_path / name / "acquired", tmp_path / name / "out"
        setup(root, tmp_path / name)
        for key, value in patches.items():
            monkeypatch.setattr(ev, key, value)
        builder(root, out, {})
    assert {"max_rows": 10**7} in seen["read"] and len(
        seen["read"]
    ) == 2  # SURF and Fugaku read up to ten million rows
    assert (
        seen["extract"] == [(1 << 30, 200)] * 3
    )  # two SURF parts (the first is empty) and the AEGIS member
    assert seen["gzip"] == [
        1 << 31,
        1 << 31,
        1 << 31,
    ]  # two Borg fragments and the Open Library prefix
