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


def test_surf_builder_ignores_parquet_members_that_are_not_parts_of_the_table(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ev, "SURF_STRIDE", 1)
    raw = tmp_path / "acquired" / "zen_surf_lisa_slurm" / SNAP / "raw"
    raw.mkdir(parents=True)
    decoy, part = tmp_path / "decoy.parquet", tmp_path / "part.parquet"
    pq.write_table(pa.Table.from_pandas(tev._surf_frame().iloc[:1], preserve_index=False), decoy)
    pq.write_table(pa.Table.from_pandas(tev._surf_frame(), preserve_index=False), part)
    with zipfile.ZipFile(raw / "slurm_table_cleaned.zip", "w") as z:
        z.write(decoy, "slurm_table_cleaned.parquet/readme.parquet")  # not a part file
        z.write(part, "slurm_table_cleaned.parquet/part-00001-x.snappy.parquet")
        z.writestr(
            "slurm_table_cleaned.parquet/part-00002.txt", "x"
        )  # a part-like name that is not Parquet
    manifest: dict = {}
    ev._build_surf(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["zen_surf_lisa_slurm"]["files"]["jobs.csv"]["rows"] == 3


def test_met_builder_counts_every_unreadable_file_and_writes_sorted_keys(tmp_path):
    raw = tmp_path / "acquired" / "met_museum_objects" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "obj_1.json").write_text('{"title": "b", "objectID": 1, "a": {"z": 1, "y": 2}}')
    (raw / "obj_2.json").write_text("not json")
    (raw / "obj_3.json").write_text("{broken")
    manifest: dict = {}
    ev._build_met(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["met_museum_objects"]["sampling"]["unreadable"] == 2
    line = (tmp_path / "o" / "met_museum_objects" / "objects.jsonl").read_text().strip()
    assert line == '{"a": {"y": 2, "z": 1}, "objectID": 1, "title": "b"}'


def test_dvf_view_keeps_numbers_in_area_and_room_columns_and_their_types():
    out = ev.dvf_view(tev._dvf_frame())
    row = out[out["mutation"] == ev.pseudonym("2024-1")].iloc[0]
    assert row["built_area_m2"] == 50.0 and row["rooms"] == 2.0 and row["value_eur"] == 346.5
    assert out["built_area_m2"].notna().sum() >= 2 and out["rooms"].notna().sum() >= 2


def test_the_xes_builder_passes_the_trace_limit_and_the_case_modulo_from_the_spec(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    folder = root / "4tu_m" / SNAP / "raw"
    folder.mkdir(parents=True)
    traces = "".join(
        f'<trace><string key="concept:name" value="c{i}"/><event><string key="concept:name" value="A"/>'  # noqa: E501
        f'<date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event></trace>'
        for i in range(12)
    )
    (folder / "log.xes").write_text(f"<log>{traces}</log>")
    monkeypatch.setattr(
        ev,
        "XES_SPECS",
        {
            "4tu_m": {
                "file": "log.xes",
                "modulo": 1,
                "numeric": [],
                "partial": False,
                "max_traces": 5,
            }
        },
    )
    manifest: dict = {}
    ev._build_xes(root, tmp_path / "o", manifest)
    sampling = manifest["4tu_m"]["sampling"]
    assert (
        sampling["stop"] == "trace_limit"
        and sampling["cases_kept"] == 5
        and sampling["stream_complete"] is False
    )
    monkeypatch.setattr(
        ev,
        "XES_SPECS",
        {"4tu_m": {"file": "log.xes", "modulo": 1, "numeric": [], "partial": False}},
    )
    full: dict = {}
    ev._build_xes(root, tmp_path / "o2", full)
    assert (
        full["4tu_m"]["sampling"]["cases_kept"] == 12
        and full["4tu_m"]["sampling"]["stop"] == "log_closed"
    )


def test_csv_events_use_the_declared_time_format_even_when_another_reading_is_possible():
    frame = pd.DataFrame(
        {
            "c": ["a", "a"],
            "t": ["01-02-2020 10:00:00", "03-02-2020 10:00:00"],
            "act": ["x", "y"],
            "n": ["1", "2"],
            "r": ["u", "u"],
        }
    )
    spec = {
        "case": "c",
        "activity": "act",
        "time": "t",
        "format": "%d-%m-%Y %H:%M:%S",
        "order": "n",
        "resource": "r",
        "modulo": 1,
    }
    out, info = ev.csv_event_view(frame, spec)
    assert out["time"].dt.month.tolist() == [2, 2] and out["time"].dt.day.tolist() == [
        1,
        3,
    ]  # day first, as declared
    assert str(out["time"].dtype).endswith("UTC]") and info["rows_without_time"] == 0


def test_clue_times_are_utc_aware():
    out = ev.clue_events_view([tev._clue(1), tev._clue(2)])
    assert str(out["time"].dtype).endswith("UTC]")


def test_table_sets_keep_a_present_optional_table_and_read_tab_files_with_embedded_separators_strictly(  # noqa: E501
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "src" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "d.zip", "w") as z:
        z.writestr(
            "p/a.csv", '"k"\t"v"\n"1"\t"x"\n"2"\t"has\ttab"\n"3"\t"z"\n'
        )  # the second row has an extra field
        z.writestr("p/opt.csv", '"k"\n"1"\n')
    monkeypatch.setattr(ev, "TABLE_SETS", {"src": {
        "archive": {"file": "d.zip", "prefix": "p/"}, "dropped": [],
        "tables": {"a": {"keep": ["k", "v"], "pseudonymise": ["k"]}, "opt": {"keep": ["k"], "optional": True}},  # noqa: E501
        "relations": []}})  # fmt: skip
    seen = []
    real = aq.extract_member
    monkeypatch.setattr(aq, "extract_member", lambda *a: seen.append(a[3:]) or real(*a))
    manifest: dict = {}
    ev._build_tables(root, tmp_path / "o", manifest)
    folder = tmp_path / "o" / "src"
    table = pd.read_csv(folder / "a.csv", dtype=str)
    assert table["v"].tolist() == [
        "x",
        "z",
    ]  # the malformed row is skipped, the quotes are stripped
    assert table["k"].tolist() == [ev.pseudonym("1"), ev.pseudonym("3")] and list(
        table.columns
    ) == ["k", "v"]
    assert (folder / "opt.csv").exists() and "optional tables absent" not in manifest["src"][
        "notes"
    ]
    assert seen == [(1 << 30, 200), (1 << 30, 200)]


def test_pseudonymisation_leaves_blank_and_missing_values_as_they_are(tmp_path, monkeypatch):
    root = tmp_path / "acquired"
    raw = root / "src" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "t.csv").write_text("k,v\n1,a\n,b\n3,c\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"src": {"sep": ",", "quote_none": False, "dropped": [],
        "tables": {"t": {"keep": ["k", "v"], "pseudonymise": ["k"]}}, "relations": []}})  # fmt: skip  # noqa: E501
    ev._build_tables(root, tmp_path / "o", {})
    table = pd.read_csv(tmp_path / "o" / "src" / "t.csv", dtype=str, keep_default_na=False)
    assert table["k"].tolist() == [ev.pseudonym("1"), "nan", ev.pseudonym("3")] or table[
        "k"
    ].tolist()[1] in ("", "nan")
    assert table["k"].iloc[0] != "1" and table["k"].iloc[2] != "3"


def test_pbdb_builder_needs_exactly_one_parquet_member_and_all_columns(tmp_path):
    raw = tmp_path / "acquired" / "zen_pbdb" / SNAP / "raw"
    raw.mkdir(parents=True)
    frame = tev._pbdb_frame()
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), tmp_path / "o.parquet")
    pq.write_table(
        pa.Table.from_pandas(frame.drop(columns=["lat"]), preserve_index=False),
        tmp_path / "n.parquet",
    )
    with zipfile.ZipFile(raw / "pbdb_parquet.zip", "w") as z:
        z.write(tmp_path / "o.parquet", "a.parquet")
        z.write(tmp_path / "o.parquet", "b.parquet")
    with pytest.raises(ev.ViewError, match="expected one Parquet member, found 2"):
        ev._build_pbdb(tmp_path / "acquired", tmp_path / "o", {})
    with zipfile.ZipFile(raw / "pbdb_parquet.zip", "w") as z:
        z.write(tmp_path / "n.parquet", "a.parquet")
    with pytest.raises(ev.ViewError, match="columns not found: .*'lat'"):
        ev._build_pbdb(tmp_path / "acquired", tmp_path / "o", {})
    with zipfile.ZipFile(raw / "pbdb_parquet.zip", "w") as z:
        z.write(tmp_path / "o.parquet", "a.parquet")
    manifest: dict = {}
    ev._build_pbdb(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["zen_pbdb"]["sampling"]["stride"] == ev.PBDB_STRIDE == 10
    assert (
        manifest["zen_pbdb"]["sampling"]["rows_kept"] == 1
        and manifest["zen_pbdb"]["sampling"]["member"] == "a.parquet"
    )


def test_new_builders_pass_the_extraction_limits_and_exact_error_messages(tmp_path, monkeypatch):
    seen = []
    real = aq.extract_member
    monkeypatch.setattr(
        aq, "extract_member", lambda *a, **k: seen.append((a[1], k)) or real(*a, **k)
    )
    raw = tmp_path / "acquired" / "zen_kelmarsh" / SNAP / "raw"
    raw.mkdir(parents=True)
    tev._kelmarsh_zip(raw / "Kelmarsh_SCADA_2016_3082.zip", turbines=(1,))
    ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", {})
    pb = tmp_path / "acquired" / "zen_pbdb" / SNAP / "raw"
    pb.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(tev._pbdb_frame(), preserve_index=False), tmp_path / "o.parquet"
    )
    with zipfile.ZipFile(pb / "pbdb_parquet.zip", "w") as z:
        z.write(tmp_path / "o.parquet", "a.parquet")
    ev._build_pbdb(tmp_path / "acquired", tmp_path / "o", {})
    assert [k for _, k in seen] == [{"max_bytes": 1 << 30, "max_ratio": 200}] * 2
    with pytest.raises(ev.ViewError, match=r"^column header line not found$"):
        ev._kelmarsh_header(["x"])
    empty = tmp_path / "acquired" / "zen_bess" / SNAP / "raw"
    empty.mkdir(parents=True)
    with pytest.raises(ev.ViewError, match=r"^no feather file in the snapshot$"):
        ev._build_bess(tmp_path / "acquired", tmp_path / "o", {})
    with zipfile.ZipFile(raw / "Kelmarsh_SCADA_2016_3082.zip", "w") as z:
        z.writestr("Status_Kelmarsh_1_x.csv", "")
    with pytest.raises(ev.ViewError, match=r"^no turbine data file in the archive$"):
        ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", {})


def test_a_human_check_tolerates_items_without_claims_or_main_snaks():
    assert ev._is_human({"id": "Q1"}) is False
    assert ev._is_human({"id": "Q1", "claims": {"P31": [{"rank": "normal"}]}}) is False
    assert (
        ev._is_human(
            {
                "id": "Q1",
                "claims": {
                    "P31": [
                        {"rank": "normal"},
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}},
                    ]
                },
            }
        )
        is True
    )


def test_wikidata_builder_counts_every_missing_identifier(tmp_path):
    raw = tmp_path / "acquired" / "wikidata_entities" / SNAP / "raw"
    raw.mkdir(parents=True)
    missing = {f"Q{i}": {"id": f"Q{i}", "missing": ""} for i in (1, 2, 3)}
    (raw / "entities_00.json").write_text(
        __import__("json").dumps({"entities": {**missing, "Q9": tev._wd_item(9)}})
    )
    manifest: dict = {}
    ev._build_wikidata(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["wikidata_entities"]["sampling"]["identifiers_absent"] == 3


def test_new_views_turn_unreadable_numbers_into_missing_and_keep_flag_types():
    raw = tev._bess_frame().astype({"Power": object})
    raw.loc[0, "Power"] = "n/a"
    out = ev.bess_view(raw, "S")
    assert out["power"].isna().sum() == 1 and str(out["power"].dtype) == "float64"
    assert out["use"].dtype == bool and out["quality_flag"].dtype == bool
    km = pd.DataFrame(
        {"Date and time": ["2016-01-03 00:00:00"], **{c: ["x"] for c in ev.KELMARSH_SIGNALS}}
    )
    assert ev.kelmarsh_view(km, "T1")["wind_speed"].isna().all()
    blank = tev._pbdb_frame()
    assert ev.pbdb_occurrence_view(blank)["class"].isna().tolist() == [False, True, False, True]


def test_pbdb_builder_reads_up_to_ten_million_rows_with_the_stride_and_blank_codes_are_missing(
    tmp_path, monkeypatch
):
    seen = []
    real = pr.read_sample
    monkeypatch.setattr(pr, "read_sample", lambda *a, **k: seen.append(k) or real(*a, **k))
    raw = tmp_path / "acquired" / "zen_pbdb" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(tev._pbdb_frame(), preserve_index=False), tmp_path / "o.parquet"
    )
    with zipfile.ZipFile(raw / "pbdb_parquet.zip", "w") as z:
        z.write(tmp_path / "o.parquet", "a.parquet")
    ev._build_pbdb(tmp_path / "acquired", tmp_path / "o", {})
    assert seen[0]["max_rows"] == 10**7 and seen[0]["stride"] == ev.PBDB_STRIDE
    frame = tev._pbdb_frame()
    frame["class"] = ["", "  ", "Mammalia", None]
    assert ev.pbdb_occurrence_view(frame)["class"].isna().tolist() == [
        True,
        False,
        True,
        True,
    ]  # in occurrence order: blank, text, blank, missing


def test_a_human_check_looks_the_main_snak_up_by_its_name():
    claim = {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
    assert ev._is_human({"claims": {"P31": [claim]}}) is True
    assert ev._is_human({"claims": {"P31": [{"other": claim["mainsnak"]}]}}) is False


def test_kelmarsh_reads_a_last_header_column_that_is_a_wanted_signal(tmp_path):
    names = ["Date and time", *ev.KELMARSH_SIGNALS]
    header = "# " + ",".join(f'"{n}"' if "," in n else n for n in names)
    row = ",".join(["2016-01-03 00:00:00"] + ["2.5"] * len(ev.KELMARSH_SIGNALS))
    text = "# exported\n#\n# Turbine: Kelmarsh 1\n#\n" + header + "\n" + row + "\n"
    raw = tmp_path / "acquired" / "zen_kelmarsh" / SNAP / "raw"
    raw.mkdir(parents=True)
    tev._kelmarsh_zip(raw / "Kelmarsh_SCADA_2016_3082.zip", turbines=(1,), text=text)
    ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", {})
    out = pd.read_csv(tmp_path / "o" / "zen_kelmarsh" / "series.csv")
    assert len(out) == 1 and out["current_l1"].iloc[0] == 2.5  # the last signal of the file
