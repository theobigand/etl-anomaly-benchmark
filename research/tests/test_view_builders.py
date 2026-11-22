"""Output contracts of the view builders: every manifest field and written file, run twice.

The expected manifests live in ``view_manifests.json`` next to this file; the checksums are
compared with the written files instead of being stored.
"""

import gzip
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import experimental_views as ev  # noqa: E402
import test_experimental_views as tev  # noqa: E402

SNAP = tev.SNAP
GOLDEN_FILE = Path(__file__).with_name("view_manifests.json")


def _golden():
    return json.loads(GOLDEN_FILE.read_text()) if GOLDEN_FILE.exists() else {}


def _stripped(entry, folder=None):
    """A manifest entry without checksums: row counts, facts, sampling records and, when the
    folder is given, the header line of every written file (so column order and no index column
    are part of the contract)."""
    out = dict(entry)
    out["files"] = {name: {"rows": f["rows"]} for name, f in entry["files"].items()}
    if folder is not None:
        out["heads"] = {
            name: (folder / name).read_text().split("\n", 1)[0][:120]
            for name in sorted(entry["files"])
        }
    return out


def _check(name, builder, root, out, views, monkeypatch=None):
    """Run a builder twice, compare checksums to the files, and return the stripped manifests."""
    first, second = {}, {}
    builder(root, out, first)
    builder(root, out, second)
    assert first == second  # a rerun gives the same checksums and facts
    result = {}
    for view in views:
        for fname, entry in first[view]["files"].items():
            folder = out / view
            assert entry["sha256"] == tev._sha(folder / fname)
        result[view] = _stripped(first[view], out / view)
    expected = _golden().get(name)
    if expected is None:
        GENERATED[name] = result
    else:
        assert result == expected
    return first


GENERATED: dict = {}


@pytest.fixture(autouse=True, scope="module")
def _dump_generated():
    yield
    if GENERATED:
        Path("/tmp/generated_view_manifests.json").write_text(
            json.dumps(GENERATED, indent=1, sort_keys=True)
        )


def _surf(root, tmp):
    raw = root / "zen_surf_lisa_slurm" / SNAP / "raw"
    raw.mkdir(parents=True)
    full = pd.concat([tev._surf_frame()] * 4, ignore_index=True)
    pq.write_table(
        pa.Table.from_pandas(full, preserve_index=False), tmp / "p.parquet", row_group_size=5
    )
    empty = tmp / "e.parquet"
    pq.write_table(pa.Table.from_pandas(tev._surf_frame().iloc[:0], preserve_index=False), empty)
    with zipfile.ZipFile(raw / "slurm_table_cleaned.zip", "w") as z:
        z.write(empty, "slurm_table_cleaned.parquet/part-00000-x.snappy.parquet")
        z.write(tmp / "p.parquet", "slurm_table_cleaned.parquet/part-00003-x.snappy.parquet")
        z.writestr("slurm_table_cleaned.parquet/_SUCCESS", "")


def _fugaku(root, tmp):
    raw = root / "zen_fdata_fugaku" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(tev._fdata_frame(), preserve_index=False), raw / "21_04.parquet"
    )


def _metropt(root, tmp):
    raw = root / "zen_metropt2" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "MetroPT2_head.csv").write_bytes(
        b"timestamp,TP2,gpsLat\n2022-04-28 12:33:29.120,1.0,41.1\n2022-04-28 12:33:30.111,2.0,41.2\n2022-04-28 12:33:31.1"  # noqa: E501
    )


def _openlibrary(root, tmp):
    raw = root / "openlibrary_dump" / SNAP / "raw"
    raw.mkdir(parents=True)
    blob = gzip.compress(("\n".join(tev._ol_line(n) for n in range(1, 30)) + "\n").encode())
    (raw / "editions_head.txt.gz").write_bytes(blob[: len(blob) * 4 // 5])


def _aegis(root, tmp):
    raw = root / "zen_aegis_vehicle" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "Automotive-ResearchDataSet-VIF-AEGIS.zip", "w") as z:
        z.writestr(
            "obdData.csv",
            '"obdData_id","trip_id","obdPid","data","timestamp"\n"1","3","0C","9","2017-01-19 16:19:03.045593"\n',  # noqa: E501
        )
        z.writestr("positions.csv", '"lat","lon"\n"47.0","15.4"\n')


def _clue(root, tmp):
    raw = root / "zen_clue_lds" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "clue_head.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "clue.json", "\n".join(tev._clue(n % 50, uid=f"u{n % 4}") for n in range(400)) + "\n"
        )
    blob = (raw / "clue_head.zip").read_bytes()
    (raw / "clue_head.zip").write_bytes(blob[: len(blob) * 3 // 4])


def _xes(root, tmp):
    for name, raw_name, data in (
        (
            "4tu_a",
            "log.xes.gz",
            gzip.compress(tev.XES.replace("</event>\n</log>", "</event></trace></log>").encode()),
        ),
        ("4tu_b", "head.xes", tev.XES[: tev.XES.index('value="c3"')].encode()),
    ):
        folder = root / name / SNAP / "raw"
        folder.mkdir(parents=True)
        (folder / raw_name).write_bytes(data)


def _csv_events(root, tmp):
    raw = root / "4tu_csv" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "log.csv").write_text(
        "Incident ID;Type;Stamp;Num;Group\nI1;Open;01-01-2013 08:00:00;001;T1\nI1;Closed;02-01-2013 08:00:00;002;T1\n"  # noqa: E501
    )


def _met(root, tmp):
    raw = root / "met_museum_objects" / SNAP / "raw"
    raw.mkdir(parents=True)
    for i in (20, 5, 11):
        (raw / f"obj_{i}.json").write_text(
            json.dumps({"objectID": i, "title": f"t{i}", "artistDisplayBio": "x"})
        )
    (raw / "obj_99.json").write_text("not json")


def _ea(root, tmp):
    raw = root / "ea_hydrology_flow" / SNAP / "raw"
    raw.mkdir(parents=True)
    head = '"measure","dateTime","date","value","completeness","quality","qcode"\n'
    (raw / "flow_s1.csv").write_text(
        head + '"m1","2020-01-02T09:00:00","2020-01-02","2.5","Complete","Good",""\n'
        '"m1","2020-01-01T09:00:00","2020-01-01","1.5","Incomplete","Estimated",""\n'
    )
    (raw / "flow_s2.csv").write_text(
        head + '"m2","2020-01-01T09:00:00","2020-01-01","","Complete","Unchecked",""\n'
    )


def _dvf(root, tmp):
    raw = root / "dgfip_dvf" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "dvf_69_2024.csv.gz").write_bytes(
        gzip.compress(tev._dvf_frame().to_csv(index=False).encode())
    )


def _panels(root, tmp):
    raw = root / "zen_p" / SNAP / "raw"
    tev._w(
        raw / "p.tsv", "date\tsyndrome\tn\n2019-01-02\tARI\t2\n2019-01-01\tARI\t1\nbad\tARI\t3\n"
    )


def _borg(root, tmp):
    raw = root / "google_cluster_2019a" / SNAP / "raw"
    raw.mkdir(parents=True)
    text = "\n".join(tev._collection_line(i % 7, 100 - i, i % 4) for i in range(60)) + "\n"
    blob = gzip.compress(text.encode())
    (raw / "collection_events_head.json.gz").write_bytes(blob[: len(blob) * 3 // 4])
    text = "\n".join(tev._instance_line(i % 3, i % 5, 100 - i, i % 4) for i in range(40)) + "\n"
    (raw / "instance_events_head.json.gz").write_bytes(gzip.compress(text.encode()))


def _tables_zip(root, tmp):
    raw = root / "src_zip" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "d.zip", "w") as z:
        z.writestr("d/movies.csv", 'movieId,title,genres\n1,"A, B",x\n2,C,y\n')
        z.writestr("d/ratings.csv", "userId,movieId,rating\n1,1,5\n1,3,4\n")


def _pbdb_relational(root, tmp):
    tev._pbdb_rel_snapshot(root, tmp)


def _pbdb(root, tmp):
    raw = root / "zen_pbdb" / SNAP / "raw"
    raw.mkdir(parents=True)
    frame = pd.concat([tev._pbdb_frame().iloc[:3]] * 2, ignore_index=True)
    frame["occurrence_no"] = ["6", "5", "4", "3", "2", "1"]
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), tmp / "o.parquet")
    with zipfile.ZipFile(raw / "pbdb_parquet.zip", "w") as z:
        z.write(tmp / "o.parquet", "pbdb_occs.parquet")


def _kelmarsh(root, tmp):
    raw = root / "zen_kelmarsh" / SNAP / "raw"
    raw.mkdir(parents=True)
    tev._kelmarsh_zip(raw / "Kelmarsh_SCADA_2016_3082.zip")


def _wikidata(root, tmp):
    raw = root / "wikidata_entities" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "entities_00.json").write_text(
        json.dumps(
            {
                "entities": {
                    "Q9": tev._wd_item(9),
                    "Q4": tev._wd_item(4, "Q5"),
                    "Q3": {"id": "Q3", "missing": ""},
                }
            }
        )
    )


def _bess(root, tmp):
    import pyarrow.feather as fe

    raw = root / "zen_bess" / SNAP / "raw"
    raw.mkdir(parents=True)
    fe.write_feather(
        pa.Table.from_pandas(tev._bess_frame(), preserve_index=False), raw / "SYS.feather"
    )


def _care(root, tmp):
    tev._care_snapshot(root)


def _nvd(root, tmp):
    raw = root / "nvd_cve" / ev.NVD_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "cves_a.json").write_text(json.dumps(tev._nvd_page(["CVE-2020-2", "CVE-2018-1"])))


def _unisg(root, tmp):
    tev._unisg_snapshot(root)


def _care_a(root, tmp):
    tev._care_a_snapshot(root)


def _backblaze(root, tmp):
    tev._bb_zip(root)


def _aqs(root, tmp):
    tev._aqs_snapshot(root)


def _usgs(root, tmp):
    tev._usgs_snapshot(root)


def _wiki(root, tmp):
    tev._wiki_snapshot(root)


def _uniprot(root, tmp):
    tev._uniprot_snapshot(root)


def _osv(root, tmp):
    tev._osv_snapshot(root)


def _gfz(root, tmp):
    tev._gfz_snapshot(root)


def _dwd(root, tmp):
    tev._dwd_snapshot(root)


def _rte(root, tmp):
    tev._rte_snapshot(root)


def _tlc(root, tmp):
    tev._tlc_page(
        [{}, {"tpep_pickup_datetime": "2023-03-07T07:00:00.000", "total_amount": "0.0"}]
    ).to_csv(tev._tlc_dir(root), index=False)


def _maude_case(root, tmp):
    tev._maude_snapshot(root)


CASES = {
    "surf": (_surf, ev._build_surf, ["zen_surf_lisa_slurm"], {}),
    "pbdb": (_pbdb, ev._build_pbdb, ["zen_pbdb"], {"PBDB_STRIDE": 2}),
    "kelmarsh": (_kelmarsh, ev._build_kelmarsh, ["zen_kelmarsh"], {}),
    "wikidata": (_wikidata, ev._build_wikidata, ["wikidata_entities"], {}),
    "bess": (_bess, ev._build_bess, ["zen_bess"], {}),
    "care": (_care, ev._build_care, ["zen_care_wind_b"], {}),
    "nvd": (_nvd, ev._build_nvd, ["nvd_cve"], {}),
    "unisg": (_unisg, ev._build_unisg, ["zen_unisg_factory"], {}),
    "care_a": (_care_a, ev._build_care_a, ["zen_care_wind_a"], {}),
    "pbdb_relational": (_pbdb_relational, ev._build_pbdb_relational, ["zen_pbdb_relational"], {"PBDB_STRIDE": 1}),  # noqa: E501
    "backblaze": (_backblaze, ev._build_backblaze, ["backblaze_drive_stats"], {"BACKBLAZE_DAYS": 2}),  # noqa: E501
    "aqs": (_aqs, ev._build_aqs, ["epa_aqs_ozone_hourly"], {"AQS_MONITORS": 2}),
    "usgs": (_usgs, ev._build_usgs, ["usgs_continuous_discharge"], {}),
    "wiki": (_wiki, ev._build_wiki, ["wikimedia_simplewiki_edits"], {}),
    "uniprot": (_uniprot, ev._build_uniprot, ["uniprot_kb_reviewed"], {}),
    "osv": (_osv, ev._build_osv_go, ["osv_go_advisories"], {}),
    "gfz": (_gfz, ev._build_gfz_kp, ["gfz_kp_index"], {}),
    "dwd": (_dwd, ev._build_dwd, ["dwd_hourly_climate"], {}),
    "rte": (_rte, ev._build_rte, ["rte_eco2mix_national"], {}),
    "tlc": (_tlc, ev._build_tlc, ["nyc_tlc_yellow"], {}),
    "maude": (_maude_case, ev._build_maude, ["openfda_device_event"], {}),
    "fugaku": (_fugaku, ev._build_fugaku, ["zen_fdata_fugaku"], {}),
    "metropt": (_metropt, ev._build_metropt, ["zen_metropt2"], {}),
    "openlibrary": (_openlibrary, ev._build_openlibrary, ["openlibrary_dump"], {"OPENLIBRARY_MODULO": 1}),  # noqa: E501
    "aegis": (_aegis, ev._build_aegis, ["zen_aegis_vehicle"], {}),
    "clue": (_clue, ev._build_clue, ["zen_clue_lds"], {"CLUE_MAX_EVENTS": 100}),
    "xes": (_xes, ev._build_xes, ["4tu_a", "4tu_b"], {"XES_SPECS": {
        "4tu_a": {"file": "log.xes.gz", "modulo": 1, "numeric": ["amount"], "partial": False},
        "4tu_b": {"file": "head.xes", "modulo": 1, "numeric": [], "partial": True}}}),
    "csv_events": (_csv_events, ev._build_csv_events, ["4tu_csv"], {"CSV_EVENT_SPECS": {"4tu_csv": {**tev.CSV_SPEC, "file": "log.csv"}}}),  # noqa: E501
    "met": (_met, ev._build_met, ["met_museum_objects"], {}),
    "ea": (_ea, ev._build_ea, ["ea_hydrology_flow"], {"EA_STATIONS": ["s1", "s2"]}),
    "dvf": (_dvf, ev._build_dvf, ["dgfip_dvf"], {}),
    "panels": (_panels, ev._build_panels, ["panels"], {"PANEL_SPECS": {"p": {"source": "zen_p", "file": "p.tsv", "sep": "\t", "time": ["date"], "format": "%Y-%m-%d", "keys": ["syndrome"]}}}),  # noqa: E501
    "borg": (_borg, ev._build_borg, ["google_cluster_2019a"], {"BORG_MAX_LINES": 25}),
    "tables_zip": (_tables_zip, ev._build_tables, ["src_zip"], {"TABLE_SETS": {"src_zip": {
        "archive": {"file": "d.zip", "prefix": "d/", "ext": ".csv"}, "sep": ",", "quote_none": False, "dropped": ["title"],  # noqa: E501
        "tables": {"movies": {"keep": ["movieId", "genres"]}, "ratings": {"keep": ["userId", "movieId"]},  # noqa: E501
                   "calendar": {"keep": ["x"], "optional": True}},
        "relations": [["ratings", "movieId", "movies", "movieId"]]}}}),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(CASES))
def test_builder_output_contract(name, tmp_path, monkeypatch):
    setup, builder, views, patches = CASES[name]
    root, out = tmp_path / "acquired", tmp_path / "out" / "deep"
    setup(root, tmp_path)
    for attribute, value in patches.items():
        monkeypatch.setattr(ev, attribute, value)
    first = _check(name, builder, root, out, views)
    for view in views:
        assert set(first[view]) >= {"files", "dropped", "pseudonymised", "source_snapshot"}


# --- exact frames of the sequence and event views ------------------------------------------------


def test_borg_instance_view_returns_every_field_in_order_and_keeps_the_source_order_of_ties():
    lines = [
        tev._instance_line(1, 1, 50, 6),
        tev._instance_line(1, 0, 40, 3),
        tev._instance_line(1, 1, 10, 0, machine=""),
        tev._instance_line(
            1, 1, 10, 4
        ),  # same instance and time as the line above: source order stays
    ]
    out = ev.borg_instance_view(lines)
    assert out.columns.tolist() == [
        "collection_id", "instance_index", "time_us", "type", "collection_type", "priority",
        "scheduling_class", "machine_id", "cpus", "memory",
    ]  # fmt: skip
    first = out.iloc[0].to_dict()
    assert first["collection_id"] == 1 and first["instance_index"] == 0 and first["time_us"] == 40
    assert first["type"] == 3 and first["collection_type"] == 0 and first["priority"] == 114
    assert (
        first["scheduling_class"] == 0
        and first["machine_id"] == 9
        and first["cpus"] == 0.5
        and first["memory"] == 0.25
    )
    assert out["type"].tolist() == [3, 0, 4, 6]  # ties at (instance 1, time 10) keep 0 before 4
    assert str(out["cpus"].dtype) == "float64" and str(out["time_us"].dtype) == "int64"


def test_borg_collection_view_keeps_the_source_order_of_ties_and_every_field():
    lines = [
        tev._collection_line(1, 10, 3),
        tev._collection_line(1, 10, 0),
        tev._collection_line(1, 5, 7),
    ]
    out = ev.borg_collection_view(lines)
    assert out["type"].tolist() == [7, 3, 0]
    row = out.iloc[0].to_dict()
    assert row == {"collection_id": 1, "time_us": 5, "type": 7, "collection_type": 0, "priority": 103,  # noqa: E501
                   "scheduling_class": 1, "scheduler": 1, "vertical_scaling": 2}  # fmt: skip


def test_xes_view_normalises_times_to_utc_types_numbers_and_reads_trace_level_numbers():
    traces = [
        {"case": "b", "attributes": {"amt": 9}, "events": [
            {"concept:name": "A", "time:timestamp": "2020-01-01T12:00:00+02:00", "org:resource": "r"},  # noqa: E501
            {"concept:name": "B", "time:timestamp": "2020-01-01T11:00:00.500+00:00", "amt": 2}]},
        {"case": "a", "attributes": {}, "events": [{"concept:name": "C", "time:timestamp": "2020-01-02T00:00:00Z"}]},  # noqa: E501
    ]  # fmt: skip
    out = ev.xes_view(traces, modulo=1, numeric=["amt"])
    assert out.columns.tolist() == [
        "case_id",
        "position",
        "time",
        "activity",
        "transition",
        "resource",
        "amt",
    ]
    assert out["case_id"].tolist() == ["a", "b", "b"]
    assert str(out["time"].dtype) == "datetime64[us, UTC]" or str(out["time"].dtype).endswith(
        ", UTC]"
    )
    assert out["time"].tolist()[1] == pd.Timestamp(
        "2020-01-01 10:00:00", tz="UTC"
    )  # +02:00 converted
    assert out["time"].tolist()[2] == pd.Timestamp("2020-01-01 11:00:00.5", tz="UTC")
    assert str(out["amt"].dtype) == "float64"
    assert (
        out["amt"].iloc[1] == 9.0 and out["amt"].iloc[2] == 2.0
    )  # event value wins, else the trace's
    assert pd.isna(out["amt"].iloc[0]) and out["resource"].iloc[1] == ev.pseudonym("r")
    empty = ev.xes_view([], modulo=1, numeric=["amt"])
    assert len(empty) == 0 and empty.columns.tolist()[-1] == "amt"


def test_table_sets_default_to_csv_members_quote_none_and_double_quote_stripping(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "src" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "d.zip", "w") as z:
        z.writestr("p/a.csv", 'k\tv\n"1"\t"x y"\n"2"\t"z"\n')
        z.writestr("p/b.csv", "k\tw\n1\tq\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"src": {
        "archive": {"file": "d.zip", "prefix": "p/"}, "dropped": [],
        "tables": {"a": {"keep": ["k", "v"]}, "b": {"keep": ["k", "w"], "strip": "q"}},
        "relations": [["a", "k", "b", "k"]]}})  # fmt: skip
    manifest = {}
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "src"
    assert (
        folder / "a.csv"
    ).read_text() == "k,v\n1,x y\n2,z\n"  # tab separated, quotes stripped, .csv member
    assert (folder / "b.csv").read_text() == "k,w\n1,\n"  # a custom strip set replaces the quote
    assert manifest["src"]["relations"] == [{"child": "a.k", "parent": "b.k", "checked": 2, "orphans": 1, "share": 0.5}]  # fmt: skip  # noqa: E501


def test_relations_with_an_absent_child_or_parent_are_dropped_when_the_table_is_optional(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "src" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "d.zip", "w") as z:
        z.writestr("a.txt", "k\n1\n")
        z.writestr("b.txt", "k\n1\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"src": {
        "archive": {"file": "d.zip", "prefix": "", "ext": ".txt"}, "sep": ",", "quote_none": False, "dropped": [],  # noqa: E501
        "tables": {"a": {"keep": ["k"]}, "b": {"keep": ["k"]}, "c": {"keep": ["k"], "optional": True}},  # noqa: E501
        "relations": [["c", "k", "a", "k"], ["a", "k", "c", "k"], ["a", "k", "b", "k"]]}})  # fmt: skip  # noqa: E501
    manifest = {}
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    assert [r["child"] for r in manifest["src"]["relations"]] == [
        "a.k"
    ]  # only the relation between present tables
    assert manifest["src"]["notes"].endswith("optional tables absent from the archive: c")


def test_table_sets_read_gzip_tables_by_extension_and_pseudonymise_listed_columns_consistently(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "clin" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "pat.csv.gz").write_bytes(gzip.compress(b"pid,sex,note\n7,F,a\n8,M,b\n"))
    (raw / "adm.csv.gz").write_bytes(gzip.compress(b"pid,adm\n7,1\n7,2\n9,3\n"))
    monkeypatch.setattr(ev, "TABLE_SETS", {"clin": {
        "ext": ".csv.gz", "sep": ",", "quote_none": False, "dropped": ["note"],
        "tables": {"pat": {"keep": ["pid", "sex"], "pseudonymise": ["pid"]},
                   "adm": {"keep": ["pid", "adm"], "pseudonymise": ["pid"]}},
        "relations": [["adm", "pid", "pat", "pid"]]}})  # fmt: skip
    manifest = {}
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "clin"
    pat = pd.read_csv(folder / "pat.csv", dtype=str)
    adm = pd.read_csv(folder / "adm.csv", dtype=str)
    assert pat["pid"].tolist() == [ev.pseudonym("7"), ev.pseudonym("8")] and "note" not in pat
    assert adm["pid"].tolist() == [ev.pseudonym("7"), ev.pseudonym("7"), ev.pseudonym("9")]
    view = manifest["clin"]
    assert view["pseudonymised"] == ["adm.pid", "pat.pid"] and view["salt_label"] == ev.SALT
    assert view["relations"] == [{"child": "adm.pid", "parent": "pat.pid", "checked": 3, "orphans": 1, "share": 1 / 3}]  # fmt: skip  # noqa: E501


def test_flat_builder_writes_one_view_per_selected_table_and_records_the_cleaning(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    (tmp_path / "pool").mkdir()
    (tmp_path / "uci_wave2").mkdir()
    frame = pd.DataFrame({"a": range(10), "b": [1.5] * 10, "c": list("xyxyxyxyxy")})
    frame.to_csv(tmp_path / "pool" / "7.csv", index=False)
    frame.assign(d=range(10)).to_csv(tmp_path / "uci_wave2" / "8.csv", index=False)
    selection = tmp_path / "sel.json"
    selection.write_text(json.dumps({"views": [
        {"key": "flat_g7_C1", "source": "uci:7", "table": "uci:7", "stratum": "C1"},
        {"key": "flat_g8_C2a", "source": "uci:8", "table": "adbench:t", "stratum": "C2a"}]}))  # fmt: skip  # noqa: E501
    monkeypatch.setattr(ev, "FLAT_SELECTION", selection)
    manifest = {}
    ev._build_flat(root, tmp_path / "o" / "deep", manifest)
    ev._build_flat(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "flat"
    assert (folder / "flat_g7_C1.csv").read_text().splitlines()[0] == "a,c" and len(
        pd.read_csv(folder / "flat_g7_C1.csv")
    ) == 10
    assert pd.read_csv(folder / "flat_g8_C2a.csv").columns.tolist() == ["a", "c", "d"]
    one = manifest["flat_g7_C1"]
    assert one == {
        "files": {"flat_g7_C1.csv": {"sha256": tev._sha(folder / "flat_g7_C1.csv"), "rows": 10}},
        "dropped": ["b"], "pseudonymised": [],
        "sampling": {"rows_in": 10, "stride": 1, "method": "every stride-th row from the first; the table is read as published"},  # noqa: E501
        "table": "uci:7", "stratum": "C1", "source_snapshot": "uci:7 (repository file pinned by checksum)",  # noqa: E501
    }  # fmt: skip
    assert (
        manifest["flat_g8_C2a"]["table"] == "adbench:t"
        and manifest["flat_g8_C2a"]["stratum"] == "C2a"
    )
