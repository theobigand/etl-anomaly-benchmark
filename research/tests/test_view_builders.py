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


def _stripped(entry):
    """A manifest entry without checksums: the row counts, facts and sampling records."""
    out = dict(entry)
    out["files"] = {name: {"rows": f["rows"]} for name, f in entry["files"].items()}
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
        result[view] = _stripped(first[view])
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


CASES = {
    "surf": (_surf, ev._build_surf, ["zen_surf_lisa_slurm"], {}),
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
