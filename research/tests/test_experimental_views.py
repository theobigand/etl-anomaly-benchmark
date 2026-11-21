import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import experimental_views as ev  # noqa: E402


def test_pseudonyms_are_stable_salted_and_keep_missing_values_missing():
    a = ev.pseudonym("https://openalex.org/A1", "s1")
    assert a == ev.pseudonym("https://openalex.org/A1", "s1") and len(a) == 16
    assert a != ev.pseudonym("https://openalex.org/A1", "s2")
    assert a != ev.pseudonym("https://openalex.org/A2", "s1")
    assert ev.pseudonym(None, "s1") is None


WORKS = [
    {
        "id": "https://openalex.org/W1",
        "publication_year": 2023,
        "type": "article",
        "cited_by_count": 3,
        "language": "en",
        "open_access": {"is_oa": True},
        "referenced_works": ["x", "y"],
        "primary_location": {"source": {"id": "https://openalex.org/S1"}},
        "authorships": [
            {
                "author_position": "first",
                "author": {"id": "https://openalex.org/A1", "display_name": "Ann", "orcid": "o"},
                "institutions": [{"id": "https://openalex.org/I1", "display_name": "U"}],
            },
            {
                "author_position": "last",
                "author": {"id": "https://openalex.org/A2"},
                "institutions": [],
            },
        ],
    }
]
AUTHORS = [
    {"id": "https://openalex.org/A1", "works_count": 4, "cited_by_count": 9, "display_name": "Ann"},
    {"id": "https://openalex.org/A2", "works_count": 1, "cited_by_count": 0},
]
INSTS = [
    {"id": "https://openalex.org/I1", "country_code": "FR", "type": "education", "works_count": 7}
]
SRCS = [{"id": "https://openalex.org/S1", "type": "journal", "works_count": 5, "is_oa": False}]


def test_openalex_views_drop_names_and_orcid_and_keep_every_foreign_key_resolvable():
    tables = ev.openalex_views(WORKS, AUTHORS, INSTS, SRCS, salt="s")
    for frame in tables.values():
        assert not {"display_name", "orcid"} & set(frame.columns)
    assert set(tables) == {"works", "authorships", "authors", "institutions", "sources"}
    assert "A1" not in "".join(tables["authors"]["author_id"])  # pseudonymised
    assert set(tables["authorships"]["author_id"]) <= set(tables["authors"]["author_id"])
    assert set(tables["authorships"]["work_id"]) <= set(tables["works"]["work_id"])
    assert set(tables["authorships"]["institution_id"].dropna()) <= set(
        tables["institutions"]["institution_id"]
    )
    assert tables["works"].loc[0, "n_references"] == 2 and tables["works"].loc[0, "n_authors"] == 2
    assert len(tables["authorships"]) == 2  # an author without institution keeps one row


def test_a_tsf_becomes_a_wide_frame_on_a_regular_time_index():
    parsed = {
        "frequency": "hourly",
        "series": [
            {"name": "a", "start": "2020-01-01 00-00-00", "values": [1.0, 2.0, None]},
            {"name": "b", "start": "2020-01-01 01-00-00", "values": [5.0, 6.0]},
        ],
    }
    frame = ev.tsf_wide(parsed)
    assert list(frame.columns) == ["a", "b"]
    assert frame.index[0] == pd.Timestamp("2020-01-01 00:00") and len(frame) == 3
    assert pd.isna(frame.loc[pd.Timestamp("2020-01-01 00:00"), "b"])
    assert frame.loc[pd.Timestamp("2020-01-01 02:00"), "b"] == 6.0


def test_event_reports_lose_identifying_fields_and_sort_deterministically():
    records = [
        {
            "safetyreportid": "2",
            "receivedate": "20240102",
            "companynumb": "c",
            "authoritynumb": "a",
            "patient": {"patientsex": "1"},
        },
        {"safetyreportid": "1", "receivedate": "20240102", "companynumb": "c2"},
        {"safetyreportid": "0", "receivedate": "20240101"},
    ]
    out = ev.faers_view(records)
    assert [r["safetyreportid"] for r in out] == ["0", "1", "2"]
    assert all("companynumb" not in r and "authoritynumb" not in r for r in out)
    assert out[2]["patient"] == {"patientsex": "1"}


def test_log_views_drop_the_message_text_that_can_hold_addresses_and_hosts():
    frame = pd.DataFrame(
        {
            "LineId": [1],
            "Time": ["t"],
            "Level": ["info"],
            "Content": ["from 10.0.0.1"],
            "EventId": ["E1"],
            "EventTemplate": ["from <*>"],
        }
    )
    out = ev.loghub_view(frame)
    assert list(out.columns) == ["LineId", "Time", "Level", "EventId"]


def test_log_views_keep_only_the_listed_columns_that_exist_and_never_node_names():
    frame = pd.DataFrame(
        {
            "LineId": [1],
            "Label": ["-"],
            "Timestamp": [5],
            "Node": ["R01-M0"],
            "Content": ["x"],
            "EventId": ["E2"],
        }
    )
    assert list(ev.loghub_view(frame).columns) == ["LineId", "Label", "Timestamp", "EventId"]


def test_spend_views_share_one_schema_pseudonymise_suppliers_and_drop_free_text():
    raw = pd.DataFrame(
        {
            "﻿Department family": ["D", "D", None],
            "Entity": ["E", "E", "E"],
            "Paid Date": ["01/02/2024", "03/02/2024", None],
            "Expense type": ["Fees", "Fees", "x"],
            "Expense area": ["A", "A", "A"],
            "Supplier": ["Acme Ltd", "Acme Ltd", "J Smith"],
            "Transaction No": ["1", "2", "3"],
            "Amount": ["£1,200.50", "30", "bad"],
            "Description": ["john smith consulting", "x", "y"],
            "Post Code": ["AB1", "AB1", "CD2"],
        }
    )
    out = ev.spend_view(raw, "org")
    assert list(out.columns) == list(ev.SPEND_COLUMNS)
    assert len(out) == 2  # the row without a readable amount or date is dropped
    assert out["amount"].tolist() == [1200.5, 30.0]
    assert out["supplier_id"].nunique() == 1 and "Acme" not in out["supplier_id"].iloc[0]
    assert (out["organisation"] == "org").all()
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_spend_views_report_a_file_that_is_not_a_table_instead_of_guessing():
    import pytest

    with pytest.raises(ev.ViewError, match="columns"):
        ev.spend_view(pd.DataFrame({"x": [1]}), "org")


def test_read_spend_skips_banner_rows_and_refuses_spreadsheets_saved_as_csv():
    import pytest

    text = "Consolidated spend for May\n\nSupplier,Amount,Date,Transaction No\nA,1,01/01/2024,9\n"
    frame = ev.read_spend(text.encode("latin-1"))
    assert (
        list(frame.columns) == ["Supplier", "Amount", "Date", "Transaction No"] and len(frame) == 1
    )
    with pytest.raises(ev.ViewError, match="spreadsheet"):
        ev.read_spend(b"PK\x03\x04binary")
    with pytest.raises(ev.ViewError, match="header"):
        ev.read_spend(b"a,b\n1,2\n")


def test_food_views_drop_contributor_fields_at_every_depth_and_keep_the_structure():
    records = [
        {
            "_id": "2",
            "creator": "bob",
            "editors_tags": ["a"],
            "images": {"1": {"uploader": "bob", "sizes": {"100": {"h": 1}}}},
            "nutriments": {"fat": 1.0},
            "ingredients": [{"id": "x", "owner": "o"}, {"id": "y"}],
        },
        {"_id": "1", "last_editor": "al", "owner": "o"},
    ]
    out = ev.off_view(records)
    assert [r["_id"] for r in out] == ["1", "2"]
    text = json.dumps(out)
    for name in ("creator", "editors_tags", "uploader", "owner", "last_editor", "bob", "al"):
        assert name not in text
    assert out[1]["images"]["1"]["sizes"]["100"]["h"] == 1  # the nested structure stays
    assert out[1]["ingredients"] == [{"id": "x"}, {"id": "y"}]
    assert records[0]["creator"] == "bob"  # the input is not modified


def test_stack_views_drop_text_and_names_pseudonymise_users_and_keep_every_link():
    tables = {
        "Users": [
            {
                "Id": "5",
                "DisplayName": "Ann",
                "Location": "Paris",
                "AboutMe": "hi",
                "Reputation": "10",
                "CreationDate": "2020-01-01",
                "Views": "2",
                "UpVotes": "1",
                "DownVotes": "0",
            }
        ],
        "Posts": [
            {
                "Id": "1",
                "PostTypeId": "1",
                "OwnerUserId": "5",
                "Title": "t",
                "Body": "b",
                "Score": "3",
                "CreationDate": "2020-01-02",
                "AcceptedAnswerId": "2",
                "Tags": "|a|",
            },
            {
                "Id": "2",
                "PostTypeId": "2",
                "ParentId": "1",
                "OwnerUserId": "99",
                "Body": "c",
                "Score": "1",
                "CreationDate": "2020-01-03",
            },
        ],
        "Comments": [
            {
                "Id": "7",
                "PostId": "1",
                "UserId": "5",
                "Text": "secret",
                "Score": "0",
                "CreationDate": "x",
                "UserDisplayName": "Ann",
            }
        ],
        "Votes": [{"Id": "8", "PostId": "1", "VoteTypeId": "2", "CreationDate": "2020-01-04"}],
        "Badges": [{"Id": "9", "UserId": "5", "Name": "Teacher", "Date": "d", "Class": "3"}],
        "PostLinks": [
            {"Id": "3", "PostId": "1", "RelatedPostId": "2", "LinkTypeId": "1", "CreationDate": "d"}
        ],
    }
    views = ev.stack_views(tables, salt="s")
    text = "".join(f.to_csv() for f in views.values())
    for word in ("Ann", "Paris", "secret", "hi,", "Title"):
        assert word not in text
    assert "Body" not in views["Posts"].columns and "Text" not in views["Comments"].columns
    users = set(views["Users"]["user_id"])
    assert views["Posts"].loc[0, "owner_user_id"] in users  # a resolvable owner keeps its link
    assert (
        views["Comments"].loc[0, "user_id"] in users and views["Badges"].loc[0, "user_id"] in users
    )
    assert views["Posts"].loc[1, "owner_user_id"] == ev.pseudonym(
        "99", "s"
    )  # same mapping, orphan kept
    assert list(views["Votes"].columns) == ["vote_id", "post_id", "vote_type_id", "creation_date"]
    assert views["PostLinks"].loc[0, "related_post_id"] == "2"


def _release(i, supplier="s1", amount=100.0):
    return {
        "id": f"r{i}",
        "ocid": f"oc-{i}",
        "date": f"2022-05-{i % 28 + 1:02d}T00:00:00-04:00",
        "buyer": {"id": "b1", "name": "Dept"},
        "awards": [
            {
                "id": f"a{i}",
                "date": "2022-05-30T00:00:00-04:00",
                "items": [{"id": "", "quantity": 1, "description": "buy from Jean Tremblay"}],
                "value": {"amount": amount, "currency": "CAD"},
                "suppliers": [{"id": supplier, "name": "J Tremblay"}],
            }
        ],
        "tender": {"status": "complete", "procuringEntity": {"id": "p1", "name": "X"}},
        "parties": [
            {"id": "b1", "name": "Dept", "roles": ["buyer"], "address": {"streetAddress": "1 rue"}},
            {
                "id": supplier,
                "name": "J Tremblay",
                "roles": ["supplier"],
                "contactPoint": {"email": "a@b"},
            },
        ],
    }


def test_ocds_views_drop_names_addresses_and_free_text_but_keep_the_nesting_and_the_links():
    releases = [_release(i, supplier=f"s{i % 3}") for i in range(30)]
    nested, awards, contracts = ev.ocds_view(releases, salt="s", keep_modulo=1)
    text = json.dumps(nested)
    for word in (
        "Tremblay",
        "Dept",
        "rue",
        "a@b",
        "name",
        "address",
        "contactPoint",
        "description",
    ):
        assert word not in text
    first = nested[0]
    assert first["awards"][0]["value"]["amount"] == 100.0 and "items" in first["awards"][0]
    supplier = first["awards"][0]["suppliers"][0]["id"]
    assert supplier in {p["id"] for p in first["parties"]}  # the same pseudonym on both sides
    assert first["buyer"]["id"] == ev.pseudonym("b1", "s")
    assert list(awards.columns) == list(ev.AWARD_COLUMNS) and len(awards) == 30
    assert awards["supplier_id"].nunique() == 3 and awards["amount"].eq(100.0).all()


def test_ocds_sampling_keeps_whole_contracts_by_a_stable_hash_of_the_contract_id():
    releases = [_release(i) for i in range(400)]
    a, _, _ = ev.ocds_view(releases, salt="s", keep_modulo=10)
    b, _, _ = ev.ocds_view(list(reversed(releases)), salt="s", keep_modulo=10)
    assert sorted(r["ocid"] for r in a) == sorted(r["ocid"] for r in b)
    assert 10 < len(a) < 90
    assert [r["date"] for r in a] == sorted(r["date"] for r in a)  # fixed chronological order


def test_ocds_contracts_link_to_their_awards_and_a_process_without_awards_adds_no_rows():
    r = _release(1)
    r["contracts"] = [
        {"id": "c1", "awardID": "a1", "dateSigned": "2022-06-01T00:00:00Z", "title": "Jean T",
         "value": {"amount": 90.0, "currency": "CAD"}},
        {"id": "c2", "awardID": "zzz", "value": {"amount": 5.0, "currency": "CAD"}},
    ]  # fmt: skip
    bare = {
        "id": "r2",
        "ocid": "oc-bare",
        "date": "2022-01-01",
        "buyer": {"id": "b1"},
        "parties": [],
    }
    nested, awards, contracts = ev.ocds_view([r, bare], salt="s", keep_modulo=1)
    assert len(nested) == 2 and len(awards) == 1
    assert list(contracts.columns) == list(ev.CONTRACT_COLUMNS) and len(contracts) == 2
    assert contracts["award_id"].tolist() == ["a1", "zzz"]
    assert "Jean T" not in json.dumps(nested)  # titles are free text
    assert contracts.loc[0, "amount"] == 90.0 and contracts.loc[0, "date_signed"].startswith(
        "2022-06-01"
    )


def test_trip_views_drop_coordinates_and_names_and_derive_the_duration_without_hiding_bad_rows():
    raw = pd.DataFrame(
        {
            "ride_id": ["a", "b", "c"],
            "rideable_type": ["classic_bike", "electric_bike", "classic_bike"],
            "started_at": ["2024-09-01 10:00:00", "2024-09-01 11:00:00", "2024-09-01 12:00:00"],
            "ended_at": ["2024-09-01 10:30:00", "2024-09-01 10:00:00", "not a time"],
            "start_station_name": ["X st", "Y st", "Z st"],
            "start_station_id": ["31001", "31002", None],
            "end_station_name": ["A", "B", "C"],
            "end_station_id": ["31005", None, None],
            "start_lat": [38.9, 38.8, 38.7],
            "start_lng": [-77.0, -77.1, -77.2],
            "end_lat": [38.9, None, None],
            "end_lng": [-77.0, None, None],
            "member_casual": ["member", "casual", "member"],
        }
    )
    out = ev.trip_view(raw)
    assert list(out.columns) == list(ev.TRIP_COLUMNS)
    text = out.to_csv()
    for word in ("X st", "38.9", "-77"):
        assert word not in text
    assert len(out) == 3  # nothing is silently dropped
    assert out["duration_min"].iloc[0] == 30.0
    assert out["duration_min"].iloc[1] == -60.0  # an impossible trip stays visible
    assert pd.isna(out["duration_min"].iloc[2])
    import pytest

    with pytest.raises(ev.ViewError, match="columns"):
        ev.trip_view(pd.DataFrame({"x": [1]}))


def test_zip_members_skip_macos_resource_forks_and_keep_real_csv_files():
    names = ["a.csv", "__MACOSX/._a.csv", "dir/._b.csv", "dir/b.csv", "readme.txt"]
    assert ev.csv_members(names) == ["a.csv", "dir/b.csv"]


# --- every builder, on a tiny raw tree, with exact outputs and exact input paths ---------------

SNAP = "2026-11-21"


def _w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _ocds_release(i, supplier="s1"):
    return {
        "id": f"r{i}",
        "ocid": f"oc-{i}",
        "date": f"2022-05-{i % 28 + 1:02d}",
        "buyer": {"id": "b"},
        "awards": [
            {
                "id": f"a{i}",
                "date": "2022-05-30",
                "value": {"amount": 10.0, "currency": "CAD"},
                "suppliers": [{"id": supplier}],
            }
        ],
        "parties": [{"id": "b"}, {"id": supplier}],
    }


def _raw_tree(tmp_path, monkeypatch):
    import gzip
    import json
    import subprocess
    import zipfile
    from pathlib import Path

    root = tmp_path / "acquired"
    raw = root / "openalex_works" / SNAP / "raw"
    _w(
        raw / "works_1.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/W2",
                        "publication_year": 2022,
                        "type": "article",
                        "cited_by_count": 1,
                        "language": "fr",
                        "open_access": {"is_oa": False},
                        "referenced_works": [],
                        "primary_location": None,
                        "authorships": [],
                    }
                ]
            }
        ),
    )
    _w(
        raw / "works_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/W1",
                        "publication_year": 2023,
                        "type": "article",
                        "cited_by_count": 3,
                        "language": "en",
                        "open_access": {"is_oa": True},
                        "referenced_works": ["x", "y"],
                        "primary_location": {"source": {"id": "https://o/S1"}},
                        "authorships": [
                            {
                                "author_position": "first",
                                "author": {"id": "https://o/A1", "display_name": "Ann"},
                                "institutions": [{"id": "https://o/I1"}],
                            }
                        ],
                    }
                ]
            }
        ),
    )
    _w(
        raw / "authors_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/A1",
                        "works_count": 4,
                        "cited_by_count": 9,
                        "display_name": "Ann",
                    }
                ]
            }
        ),
    )
    _w(
        raw / "institutions_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/I1",
                        "country_code": "FR",
                        "type": "education",
                        "works_count": 7,
                    }
                ]
            }
        ),
    )
    _w(
        raw / "sources_0.json",
        json.dumps(
            {
                "results": [
                    {"id": "https://o/S1", "type": "journal", "works_count": 5, "is_oa": False}
                ]
            }
        ),
    )
    tsf = (
        "@attribute series_name string\n@attribute start_timestamp date\n@frequency hourly\n@data\n"
    )
    tsf += "a:2020-01-01 00-00-00:1,2\nb:2020-01-01 01-00-00:5,6\n"
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", tsf)
    events = root / "openfda_drug_event" / SNAP / "raw"
    _w(
        events / "event_1.json",
        json.dumps(
            {
                "results": [
                    {
                        "safetyreportid": "2",
                        "receivedate": "20240102",
                        "companynumb": "c",
                        "patient": {"s": 1},
                    }
                ]
            }
        ),
    )
    _w(
        events / "event_0.json",
        json.dumps(
            {"results": [{"safetyreportid": "1", "receivedate": "20240101", "authoritynumb": "a"}]}
        ),
    )
    head = "LineId,Time,Level,Content,EventId,EventTemplate\n"
    _w(tmp_path / "loghub" / "B.csv", head + "1,t,info,from 10.0.0.1,E1,from <*>\n")
    _w(tmp_path / "loghub" / "A.csv", head + "1,t,warn,x,E2,x\n2,t2,warn,y,E3,y\n")
    food = root / "openfoodfacts_products" / SNAP / "raw" / "d.json.gz"
    food.parent.mkdir(parents=True)
    with gzip.open(food, "wt") as handle:
        handle.write(
            json.dumps({"_id": "2", "creator": "bob", "a": {"uploader": "u", "k": 1}}) + "\n\n"
        )
        handle.write(json.dumps({"_id": "1", "owner": "o"}) + "\n")
    dump = root / "stackexchange_dump" / SNAP / "raw"
    dump.mkdir(parents=True)
    (dump / "zed.stackexchange.com.7z").write_bytes(b"x")
    (dump / "abc.stackexchange.com.7z").write_bytes(b"x")
    xml = {
        "Users": '<users><row Id="5" DisplayName="Ann" Reputation="10" CreationDate="d" Views="1" UpVotes="2" DownVotes="3"/></users>',  # noqa: E501
        "Posts": '<posts><row Id="1" PostTypeId="1" OwnerUserId="5" Title="t" Body="b" Score="3" CreationDate="d"/></posts>',  # noqa: E501
    }

    def fake_run(command, check):
        target = Path(command[command.index("-C") + 1])
        for name, text in xml.items():
            (target / f"{name}.xml").write_text(text)

    monkeypatch.setattr(subprocess, "run", fake_run)
    for source in ("ocds_montreal", "ocds_georgia", "ocds_zambia"):
        path = root / source / SNAP / "raw" / "full.jsonl.gz"
        path.parent.mkdir(parents=True)
        with gzip.open(path, "wt") as handle:
            for i in range(60):
                handle.write(json.dumps(_ocds_release(i)) + "\n")
    csv = (
        "ride_id,rideable_type,started_at,ended_at,start_station_id,end_station_id,member_casual\n"
    )
    csv += "r2,e,2024-09-02 10:00:00,2024-09-02 10:10:00,1,2,member\n"
    csv += "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,3,,casual\n"
    for source in ("bikeshare_capital", "bikeshare_jc"):
        folder = root / source / SNAP / "raw"
        folder.mkdir(parents=True)
        with zipfile.ZipFile(folder / "b.zip", "w") as z:
            z.writestr("a.csv", csv)
            z.writestr("__MACOSX/._a.csv", "junk")
        with zipfile.ZipFile(folder / "a.zip", "w") as z:
            z.writestr("c.csv", csv.replace("r2", "r3"))
    import io
    import tarfile

    jobs = root / "slurm_ccin2p3" / SNAP / "raw"
    jobs.mkdir(parents=True)
    data = _jobs().to_csv(sep="\t", index=False).encode()
    with tarfile.open(jobs / "07.tsv.tar.gz", "w:gz") as tar:
        info = tarfile.TarInfo("07.tsv")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    good = "Department family,Entity,Date,Expense type,Expense area,Supplier,Transaction number,Amount\n"  # noqa: E501
    good += 'D,E,01/02/2024,Fees,A,Acme,2,"£1,000.50"\nD,E,03/02/2024,Fees,A,Beta,1,30\n'
    _w(root / "ukspend_mhra" / SNAP / "raw" / "00.csv", good)
    _w(
        root / "ukspend_nhsbsa" / SNAP / "raw" / "00.csv",
        "Banner\n" + good.replace("Department family", "Dept"),
    )
    (root / "ukspend_nice" / SNAP / "raw").mkdir(parents=True)
    (root / "ukspend_nice" / SNAP / "raw" / "00.csv").write_bytes(b"PK\x03\x04")
    _w(root / "ukspend_ofsted" / SNAP / "raw" / "00.csv", "a,b\n1,2\n")
    return root


def _accessed(monkeypatch, root):
    """Exact path strings under ``root`` that the code opens or lists."""
    import builtins
    import os

    seen = []
    real_open = builtins.open
    base = str(root.parent)

    def spy_open(file, *a, **k):
        if isinstance(file, str | os.PathLike) and str(file).startswith(base):
            seen.append(str(file)[len(base) + 1 :])
        return real_open(file, *a, **k)

    import io

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    return seen


def _sha(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_openalex_builder_writes_five_sorted_tables_and_reads_the_documented_paths(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_openalex(root, out, manifest)
    reads = sorted(set(p for p in seen if p.startswith("acquired/")))
    base = "acquired/openalex_works/2026-11-21/raw"
    assert reads == sorted(
        [
            *(f"{base}/{n}_0.json" for n in ("authors", "institutions", "sources", "works")),
        ]
        + [f"{base}/works_1.json"]
    )
    texts = {f.name: f.read_text() for f in (out / "openalex").glob("*.csv")}
    assert texts == {
        "authors.csv": "author_id,works_count,cited_by_count\nd62d7796a28c16a2,4,9\n",
        "authorships.csv": "work_id,author_id,institution_id,position\nW1,d62d7796a28c16a2,I1,first\n",  # noqa: E501
        "institutions.csv": "institution_id,country_code,type,works_count\nI1,FR,education,7\n",
        "sources.csv": "source_id,type,works_count,is_oa\nS1,journal,5,False\n",
        "works.csv": "work_id,year,type,cited_by_count,language,is_oa,source_id,n_references,n_authors\n"  # noqa: E501
        "W1,2023,article,3,en,True,S1,2,1\nW2,2022,article,1,fr,False,,0,0\n",
    }
    view = manifest["openalex"]
    assert view["files"] == {
        n: {"sha256": _sha(out / "openalex" / n), "rows": rows}
        for n, rows in (
            ("authors.csv", 1),
            ("authorships.csv", 1),
            ("institutions.csv", 1),
            ("sources.csv", 1),
            ("works.csv", 2),
        )
    }
    assert {k: v for k, v in view.items() if k != "files"} == {
        "dropped": ["display_name", "orcid", "observed_orcids", "raw works ids of authors"],
        "pseudonymised": ["author_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "openalex_works/2026-11-21",
    }
    assert list(manifest) == ["openalex"]


def _record_of(manifest, view, out_dir):
    entry = manifest[view]
    return {n: {"sha256": _sha(out_dir / n), "rows": f["rows"]} for n, f in entry["files"].items()}


def test_the_monash_faers_and_log_builders_have_exact_outputs_and_manifests(tmp_path, monkeypatch):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_monash(root, out, manifest)
    ev._build_faers(root, out, manifest)
    ev._build_loghub(root, out, manifest)
    reads = sorted(set(seen))
    assert "acquired/monash_zenodo/2026-11-21/raw/4656626_pedestrian_counts_dataset.zip" in reads
    assert "acquired/openfda_drug_event/2026-11-21/raw/event_0.json" in reads
    assert "acquired/openfda_drug_event/2026-11-21/raw/event_1.json" in reads
    assert "loghub/A.csv" in reads and "loghub/B.csv" in reads
    assert (out / "monash_pedestrian" / "wide.csv").read_text() == (
        "timestamp,a,b\n2020-01-01 00:00:00,1.0,\n2020-01-01 01:00:00,2.0,5.0\n2020-01-01 02:00:00,,6.0\n"  # noqa: E501
    )
    assert (out / "openfda_drug_event" / "events.jsonl").read_text() == (
        '{"receivedate": "20240101", "safetyreportid": "1"}\n'
        '{"patient": {"s": 1}, "receivedate": "20240102", "safetyreportid": "2"}\n'
    )
    assert (
        out / "loghub" / "A.csv"
    ).read_text() == "LineId,Time,Level,EventId\n1,t,warn,E2\n2,t2,warn,E3\n"
    assert (out / "loghub" / "B.csv").read_text() == "LineId,Time,Level,EventId\n1,t,info,E1\n"
    assert manifest["monash_pedestrian"] == {
        "files": _record_of(manifest, "monash_pedestrian", out / "monash_pedestrian")
        | {"wide.csv": {"sha256": _sha(out / "monash_pedestrian" / "wide.csv"), "rows": 3}},
        "dropped": [],
        "pseudonymised": [],
        "source_snapshot": "monash_zenodo/2026-11-21",
    }
    assert manifest["openfda_drug_event"]["files"] == {
        "events.jsonl": {"sha256": _sha(out / "openfda_drug_event" / "events.jsonl"), "rows": 2}
    }
    assert {k: v for k, v in manifest["openfda_drug_event"].items() if k != "files"} == {
        "dropped": ["companynumb", "authoritynumb"],
        "pseudonymised": [],
        "source_snapshot": "openfda_drug_event/2026-11-21",
    }
    assert manifest["loghub"]["files"] == {
        "A.csv": {"sha256": _sha(out / "loghub" / "A.csv"), "rows": 2},
        "B.csv": {"sha256": _sha(out / "loghub" / "B.csv"), "rows": 1},
    }
    assert {k: v for k, v in manifest["loghub"].items() if k != "files"} == {
        "dropped": ["Content", "EventTemplate"],
        "pseudonymised": [],
        "source_snapshot": "loghub@dd61d09",
    }


def test_the_food_and_stack_builders_have_exact_outputs_and_manifests(tmp_path, monkeypatch):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_food(root, out, manifest)
    ev._build_stack(root, out, manifest)
    assert "acquired/openfoodfacts_products/2026-11-21/raw/d.json.gz" in seen
    assert (
        out / "openfoodfacts" / "products.jsonl"
    ).read_text() == '{"_id": "1"}\n{"_id": "2", "a": {"k": 1}}\n'
    assert manifest["openfoodfacts"]["files"]["products.jsonl"]["rows"] == 2
    assert {k: v for k, v in manifest["openfoodfacts"].items() if k != "files"} == {
        "dropped": sorted(ev.OFF_DROP),
        "pseudonymised": [],
        "source_snapshot": "openfoodfacts_products/2026-11-21",
    }
    for site in ("abc", "zed"):
        folder = out / "stackexchange" / site
        assert (folder / "Users.csv").read_text() == (
            "user_id,reputation,creation_date,views,up_votes,down_votes\n3e9ef5a6b3d5aa75,10,d,1,2,3\n"
        )
        assert (folder / "Posts.csv").read_text() == (
            "post_id,post_type_id,parent_id,accepted_answer_id,creation_date,score,view_count,answer_count,"
            "comment_count,tags,owner_user_id\n1,1,,,d,3,,,,,3e9ef5a6b3d5aa75\n"
        )
        assert (folder / "Votes.csv").read_text() == "vote_id,post_id,vote_type_id,creation_date\n"
    files = manifest["stackexchange"]["files"]
    assert list(files) == [
        f"{s}/{t}.csv"
        for s in ("abc", "zed")
        for t in ("Users", "Posts", "Comments", "Votes", "Badges", "PostLinks")
    ]
    assert files["abc/Users.csv"] == {
        "sha256": _sha(out / "stackexchange" / "abc" / "Users.csv"),
        "rows": 1,
    }
    assert files["zed/Comments.csv"]["rows"] == 0
    assert {k: v for k, v in manifest["stackexchange"].items() if k != "files"} == {
        "dropped": [
            "Title",
            "Body",
            "Text",
            "DisplayName",
            "Location",
            "AboutMe",
            "WebsiteUrl",
            "profile fields",
        ],
        "pseudonymised": ["user_id", "owner_user_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "stackexchange_dump/2026-11-21",
        "notes": "CC BY-SA: a redistributed derived database needs attribution and the same licence",  # noqa: E501
    }
    assert (
        "acquired/stackexchange_dump/2026-11-21/raw/abc.stackexchange.com.7z" not in seen
    )  # extractor is mocked


def test_the_procurement_builder_writes_three_sources_with_whole_hash_sampled_processes(
    tmp_path, monkeypatch
):
    import json

    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    manifest = {}
    ev._build_ocds(root, out, manifest)
    assert list(manifest) == ["ocds_montreal", "ocds_georgia", "ocds_zambia"]
    for source in manifest:
        folder = out / source
        releases = [
            json.loads(line) for line in (folder / "releases.jsonl").read_text().splitlines()
        ]
        assert [r["date"] for r in releases] == sorted(r["date"] for r in releases)
        assert 1 <= len(releases) < 60 and all("name" not in r["buyer"] for r in releases)
        assert (folder / "awards.csv").read_text().splitlines()[0] == (
            "ocid,award_id,date,amount,currency,supplier_id,buyer_id,method"
        )
        assert (
            folder / "contracts.csv"
        ).read_text() == "ocid,contract_id,award_id,date_signed,amount,currency\n"
        files = manifest[source]["files"]
        assert list(files) == ["releases.jsonl", "awards.csv", "contracts.csv"]
        assert files["releases.jsonl"] == {
            "sha256": _sha(folder / "releases.jsonl"),
            "rows": len(releases),
        }
        assert files["awards.csv"]["rows"] == len(releases) and files["contracts.csv"]["rows"] == 0
        assert {k: v for k, v in manifest[source].items() if k != "files"} == {
            "dropped": sorted(ev.OCDS_DROP),
            "pseudonymised": ["party ids"],
            "salt_label": ev.SALT,
            "sampling": "contracting processes with sha256(ocid) % 10 == 0, whole processes, by date",  # noqa: E501
            "source_snapshot": f"{source}/2026-11-21",
        }


def test_the_bikeshare_builder_skips_resource_forks_and_sorts_by_start_then_ride(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_bikeshare(root, out, manifest)
    expected = (
        "ride_id,rideable_type,started_at,ended_at,duration_min,start_station_id,end_station_id,member_casual\n"
        "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,30.0,3,,casual\n"
        "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,30.0,3,,casual\n"
        "r2,e,2024-09-02 10:00:00,2024-09-02 10:10:00,10.0,1,2,member\n"
        "r3,e,2024-09-02 10:00:00,2024-09-02 10:10:00,10.0,1,2,member\n"
    )
    for source in ("bikeshare_capital", "bikeshare_jc"):
        assert (out / source / "trips.csv").read_text() == expected
        assert manifest[source]["files"] == {
            "trips.csv": {"sha256": _sha(out / source / "trips.csv"), "rows": 4}
        }
        assert {k: v for k, v in manifest[source].items() if k != "files"} == {
            "dropped": ["station names", "start and end coordinates"],
            "pseudonymised": [],
            "source_snapshot": f"{source}/2026-11-21",
        }
        assert f"acquired/{source}/2026-11-21/raw/a.zip" in seen
        assert f"acquired/{source}/2026-11-21/raw/b.zip" in seen
    assert list(manifest) == ["bikeshare_capital", "bikeshare_jc"]


def test_the_spending_builder_reports_files_it_cannot_read_instead_of_hiding_them(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_ukspend(root, out, manifest)
    rows = "organisation,date,expense_type,expense_area,supplier_id,transaction_no,amount\n"
    for org in ("mhra", "nhsbsa"):
        assert (out / "ukspend" / f"{org}.csv").read_text() == (
            rows + f"{org},2024-02-01,Fees,A,4f37571c7ae9051b,2,1000.5\n"
            f"{org},2024-02-03,Fees,A,7f062e7195549622,1,30.0\n"
        )
    assert sorted(p.name for p in (out / "ukspend").iterdir()) == ["mhra.csv", "nhsbsa.csv"]
    view = manifest["ukspend"]
    assert list(view["files"]) == ["mhra.csv", "nhsbsa.csv"]
    assert view["files"]["mhra.csv"] == {"sha256": _sha(out / "ukspend" / "mhra.csv"), "rows": 2}
    assert view["skipped"] == {
        "nice": ["00.csv: a spreadsheet saved with a .csv name"],
        "ofsted": ["00.csv: no header line with a supplier column in the first 15 lines"],
    }
    assert {k: v for k, v in view.items() if k not in ("files", "skipped")} == {
        "dropped": [
            "Description",
            "post code",
            "supplier type",
            "VAT number",
            "contract and project codes",
        ],
        "pseudonymised": ["supplier_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "ukspend_*/2026-11-21",
    }
    for org in ("mhra", "nhsbsa", "nice", "ofsted"):
        assert f"acquired/ukspend_{org}/2026-11-21/raw/00.csv" in seen
    assert not any(
        "charity_commission" in p and p.endswith(".csv") for p in seen
    )  # no files: nothing read


def test_build_runs_every_builder_in_order_and_main_writes_the_manifest(
    tmp_path, monkeypatch, capsys
):
    import json

    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    manifest = ev.build(root, out)
    assert list(manifest) == [
        "openalex", "monash_pedestrian", "openfda_drug_event", "loghub", "openfoodfacts", "stackexchange",  # noqa: E501
        "ocds_montreal", "ocds_georgia", "ocds_zambia", "bikeshare_capital", "bikeshare_jc",
        "slurm_ccin2p3", "ukspend",  # noqa: E501
    ]  # fmt: skip
    target = tmp_path / "m.json"
    assert (
        ev.main(["--root", str(root), "--out", str(tmp_path / "out2"), "--manifest", str(target)])
        == 0
    )
    text = target.read_text()
    assert json.loads(text) == json.loads(json.dumps(manifest))
    assert text == json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    printed = capsys.readouterr().out.strip()
    assert printed == str(
        {k: sum(f["rows"] for f in v["files"].values()) for k, v in manifest.items()}
    )
    assert ev.SNAPSHOT == "2026-11-21" and ev.SALT == "etl-benchmark-views-v1"


# --- remaining exact behaviours -------------------------------------------------------------------


def _rich_release(ocid="oc-1", with_award_date=True):
    award = {
        "id": "a1",
        "value": {"amount": 12.5, "currency": "GEL"},
        "suppliers": [{"id": "s1", "name": "Sup One"}, {"id": "s2"}],
        "items": [{"id": "i", "description": "text"}],
    }
    if with_award_date:
        award["date"] = "2021-02-03"
    return {
        "id": "r1",
        "ocid": ocid,
        "date": "2021-02-01",
        "buyer": {"id": "b1", "name": "Buyer"},
        "tender": {
            "title": "t",
            "procurementMethod": "open",
            "procuringEntity": {"id": "p1", "name": "Entity"},
            "documents": [{"url": "x"}],
        },
        "parties": [
            {"id": "b1", "name": "Buyer", "address": {"x": 1}, "roles": ["buyer"]},
            {"id": "s1", "identifier": {"id": "slug"}, "roles": ["supplier"]},
        ],
        "awards": [award],
        "contracts": [
            {
                "id": "c1",
                "awardID": "a1",
                "dateSigned": "2021-03-01",
                "value": {"amount": 9.0, "currency": "GEL"},
            }
        ],
    }


def test_ocds_view_maps_every_field_of_awards_contracts_parties_and_tenders_exactly():
    nested, awards, contracts = ev.ocds_view([_rich_release()], salt="k", keep_modulo=1)
    pid = lambda v: ev.pseudonym(v, "k")  # noqa: E731
    assert nested == [
        {
            "id": "r1",
            "ocid": "oc-1",
            "date": "2021-02-01",
            "buyer": {"id": pid("b1")},
            "tender": {"procurementMethod": "open", "procuringEntity": {"id": pid("p1")}},
            "parties": [
                {"id": pid("b1"), "roles": ["buyer"]},
                {"id": pid("s1"), "roles": ["supplier"]},
            ],
            "awards": [
                {
                    "id": "a1",
                    "value": {"amount": 12.5, "currency": "GEL"},
                    "suppliers": [{"id": pid("s1")}, {"id": pid("s2")}],
                    "items": [{"id": "i"}],
                    "date": "2021-02-03",
                }
            ],
            "contracts": [
                {
                    "id": "c1",
                    "awardID": "a1",
                    "dateSigned": "2021-03-01",
                    "value": {"amount": 9.0, "currency": "GEL"},
                }
            ],
        }
    ]
    assert awards.to_dict("records") == [
        {
            "ocid": "oc-1", "award_id": "a1", "date": "2021-02-03", "amount": 12.5, "currency": "GEL",  # noqa: E501
            "supplier_id": pid("s1"), "buyer_id": pid("b1"), "method": "open",
        }
    ]  # fmt: skip
    assert contracts.to_dict("records") == [
        {
            "ocid": "oc-1",
            "contract_id": "c1",
            "award_id": "a1",
            "date_signed": "2021-03-01",
            "amount": 9.0,
            "currency": "GEL",
        }
    ]
    assert ev.CONTRACT_COLUMNS == (
        "ocid",
        "contract_id",
        "award_id",
        "date_signed",
        "amount",
        "currency",
    )
    assert ev.AWARD_COLUMNS == (
        "ocid",
        "award_id",
        "date",
        "amount",
        "currency",
        "supplier_id",
        "buyer_id",
        "method",
    )
    assert (
        frozenset(
            [
                "name",
                "address",
                "contactPoint",
                "description",
                "legalName",
                "identifier",
                "title",
                "documents",
            ]
        )
        == ev.OCDS_DROP
    )


def test_ocds_view_falls_back_on_the_release_date_and_tolerates_missing_parts():
    release = _rich_release(with_award_date=False)
    release["awards"][0]["suppliers"] = []
    del release["buyer"], release["tender"], release["parties"]
    nested, awards, _ = ev.ocds_view([release], salt="k", keep_modulo=1)
    assert awards.loc[0, "date"] == "2021-02-01"  # the award has no date: the release date
    assert awards.loc[0, "supplier_id"] is None or pd.isna(awards.loc[0, "supplier_id"])
    assert pd.isna(awards.loc[0, "buyer_id"]) and pd.isna(awards.loc[0, "method"])
    assert nested[0]["parties"] == [] and "buyer" not in nested[0]
    bare = {"id": "r", "ocid": "oc-9", "date": "d"}
    nested, awards, contracts = ev.ocds_view([bare], salt="k", keep_modulo=1)
    assert nested == [{"id": "r", "ocid": "oc-9", "date": "d", "parties": []}]
    assert len(awards) == 0 and len(contracts) == 0
    no_tender = {"id": "r", "ocid": "oc-8", "date": "d", "tender": {"procurementMethod": "m"}}
    assert ev.ocds_view([no_tender], salt="k", keep_modulo=1)[0][0]["tender"] == {
        "procurementMethod": "m"
    }


def test_the_ocds_sample_is_a_stable_hash_of_the_first_eight_hex_digits_modulo_the_divisor():
    import hashlib

    releases = [{"id": f"r{i}", "ocid": f"oc-{i}", "date": "d"} for i in range(300)]
    for modulo in (10, 7, 1):
        expected = sorted(
            r["ocid"]
            for r in releases
            if int(hashlib.sha256(r["ocid"].encode()).hexdigest()[:8], 16) % modulo == 0
        )
        got, _, _ = ev.ocds_view(releases, keep_modulo=modulo)
        assert sorted(r["ocid"] for r in got) == expected
    default, _, _ = ev.ocds_view(releases)
    assert len(default) == len(ev.ocds_view(releases, keep_modulo=10)[0]) and 5 < len(default) < 60
    assert (
        ev.ocds_view(releases, salt="a", keep_modulo=1)[0][0]
        == ev.ocds_view(releases, keep_modulo=1, salt="a")[0][0]
    )


def test_spend_views_handle_mixed_date_formats_bad_dates_optional_columns_and_missing_suppliers():
    raw = pd.DataFrame(
        {
            "Transaction No.": ["1", "2", "3", "4", "5"],
            "Date": ["01/02/2024", "2024-02-03", "not a date", "05/02/2024", "06/02/2024"],
            "Supplier": ["A", "B", "C", None, "A"],
            "Amount (GBP)": ["10", "20", "30", "40", "oops"],
        }
    )
    out = ev.spend_view(raw, "org", salt="x")
    assert out["transaction_no"].tolist() == [
        "1",
        "2",
        "4",
    ]  # bad date and bad amount rows are dropped
    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-02-01",
        "2024-02-03",
        "2024-02-05",
    ]
    assert out["expense_type"].isna().all() and out["expense_area"].isna().all()
    assert out["supplier_id"].tolist()[:2] == [ev.pseudonym("a", "x"), ev.pseudonym("b", "x")]
    assert out["supplier_id"].isna().tolist() == [False, False, True]
    assert ev.spend_view(raw, "org")["supplier_id"].iloc[0] == ev.pseudonym("a")  # the default salt
    only_amount_bad = raw.assign(Date="01/02/2024", **{"Amount (GBP)": ["10", "x", "x", "x", "x"]})
    assert len(ev.spend_view(only_amount_bad, "o")) == 1
    only_date_bad = raw.assign(Date=["01/02/2024", "x", "x", "x", "x"], **{"Amount (GBP)": "5"})
    assert len(ev.spend_view(only_date_bad, "o")) == 1
    wide = pd.DataFrame({f"c{i}": [1] for i in range(10)})
    with pytest.raises(ev.ViewError) as info:
        ev.spend_view(wide, "o")
    assert str(info.value) == "required columns not found in ['c0', 'c1', 'c2', 'c3', 'c4', 'c5']"
    full = pd.DataFrame({"Expense type": ["T"], "Expense area": ["Z"], "Date": ["01/02/2024"], "Supplier": ["S"],  # noqa: E501
                         "Transaction No": ["9"], "Amount": ["1"]})  # fmt: skip
    kept = ev.spend_view(full, "o")
    assert kept.loc[0, "expense_type"] == "T" and kept.loc[0, "expense_area"] == "Z"
    assert list(ev.SPEND_COLUMNS) == [
        "organisation", "date", "expense_type", "expense_area", "supplier_id", "transaction_no", "amount",  # noqa: E501
    ]  # fmt: skip


def test_read_spend_decodes_both_encodings_keeps_text_and_skips_broken_rows():
    header = "Supplier,Amount,Date,Transaction No\n"
    latin = (header + "Café,007,01/01/2024,9\nBroken,1,2,3,4,5\nOk,2,01/01/2024,10\n").encode(
        "latin-1"
    )
    frame = ev.read_spend(latin)
    assert frame["Supplier"].tolist() == [
        "Café",
        "Ok",
    ]  # decoded as latin-1, extra-field row skipped
    assert frame["Amount"].tolist() == ["007", "2"]  # text, not numbers
    bom = ("﻿" + header + "A,1,d,1\n").encode("utf-8")
    assert list(ev.read_spend(bom).columns)[0] == "Supplier"  # a UTF-8 BOM is not part of the name
    lines = ["banner"] * 14 + [header.strip(), "A,1,d,1"]
    assert ev.read_spend("\n".join(lines).encode())["Supplier"].tolist() == [
        "A"
    ]  # header on line 15
    lines = ["banner"] * 15 + [header.strip(), "A,1,d,1"]
    with pytest.raises(ev.ViewError, match="first 15 lines"):
        ev.read_spend("\n".join(lines).encode())  # the header on line 16 is out of range


def test_small_view_helpers_have_exact_edge_behaviour():
    assert ev.csv_members(["__macosx/a.csv", "x/__MACOSX/b.csv", "__MACOSX/c.csv", "d/._e.csv", "d/f._g.csv", "h.CSV"]) == [  # noqa: E501
        "__macosx/a.csv", "d/f._g.csv", "x/__MACOSX/b.csv",
    ]  # fmt: skip
    assert (
        ev._short("https://a/b/c") == "c"
        and ev._short("plain") == "plain"
        and ev._short(None) is None
    )
    wide = ev.tsf_wide(
        {
            "frequency": "daily",
            "series": [{"name": "a", "start": "2020-01-01 00-00-00", "values": [None, None]}],
        }
    )
    assert str(wide["a"].dtype) == "float64"
    assert [
        r["safetyreportid"]
        for r in ev.faers_view(
            [{"safetyreportid": "1", "receivedate": "20240101"}, {"safetyreportid": "2"}]
        )
    ] == ["2", "1"]
    shape = ev.openalex_views([{"id": "https://o/W1"}], [], [], [], salt="s")
    assert shape["works"].loc[0, "n_authors"] == 0 and shape["authorships"].empty
    raw = pd.DataFrame({c: ["x"] for c in "abcdefgh"})
    with pytest.raises(ev.ViewError) as info:
        ev.trip_view(raw)
    assert str(info.value) == "trip columns not found in ['a', 'b', 'c', 'd', 'e', 'f']"
    bad_start = pd.DataFrame({"ride_id": ["r"], "started_at": ["nope"], "ended_at": ["2024-01-01"],
                              "start_station_id": ["1"], "end_station_id": ["2"]})  # fmt: skip
    assert pd.isna(ev.trip_view(bad_start)["duration_min"].iloc[0])


def test_every_builder_creates_missing_parents_runs_twice_and_writes_to_the_exact_paths(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "o" / "deep"
    written = []
    import builtins
    import io

    real_open = builtins.open

    def spy(file, mode="r", *a, **k):
        if "w" in mode and str(file).startswith(str(out)):
            written.append(str(file)[len(str(out)) + 1 :])
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    for step in (
        ev._build_openalex, ev._build_monash, ev._build_faers, ev._build_loghub, ev._build_food,
        ev._build_stack, ev._build_ocds, ev._build_bikeshare, ev._build_ukspend,
    ):  # fmt: skip
        fresh = {}
        step(root, out, fresh)
        step(root, out, fresh)  # a second run over existing directories
    names = sorted(set(written))
    expected = (
        [
            f"openalex/{n}.csv"
            for n in ("authors", "authorships", "institutions", "sources", "works")
        ]
        + ["monash_pedestrian/wide.csv", "openfda_drug_event/events.jsonl"]
        + ["loghub/A.csv", "loghub/B.csv", "openfoodfacts/products.jsonl"]
        + [
            f"stackexchange/{s}/{t}.csv"
            for s in ("abc", "zed")
            for t in ("Badges", "Comments", "PostLinks", "Posts", "Users", "Votes")
        ]
        + [
            f"{s}/{f}"
            for s in ("ocds_georgia", "ocds_montreal", "ocds_zambia")
            for f in ("awards.csv", "contracts.csv", "releases.jsonl")
        ]
        + [
            "bikeshare_capital/trips.csv",
            "bikeshare_jc/trips.csv",
            "ukspend/mhra.csv",
            "ukspend/nhsbsa.csv",
        ]
    )
    assert names == sorted(expected)


def test_json_lines_views_sort_keys_and_the_tsf_decoder_replaces_bad_bytes(tmp_path, monkeypatch):
    import gzip
    import json
    import zipfile

    root = tmp_path / "acquired"
    gz = root / "openfoodfacts_products" / SNAP / "raw" / "d.json.gz"
    gz.parent.mkdir(parents=True)
    with gzip.open(gz, "wt") as handle:
        handle.write(json.dumps({"b": 1, "_id": "1", "a": {"z": 1, "y": 2}}) + "\n")
    events = root / "openfda_drug_event" / SNAP / "raw"
    _w(
        events / "event_0.json",
        json.dumps({"results": [{"safetyreportid": "1", "receivedate": "20240101", "a": 1}]}),
    )
    ev._build_food(root, tmp_path / "o", {})
    ev._build_faers(root, tmp_path / "o", {})
    assert (
        tmp_path / "o" / "openfoodfacts" / "products.jsonl"
    ).read_text() == '{"_id": "1", "a": {"y": 2, "z": 1}, "b": 1}\n'
    assert (
        tmp_path / "o" / "openfda_drug_event" / "events.jsonl"
    ).read_text() == '{"a": 1, "receivedate": "20240101", "safetyreportid": "1"}\n'
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    tsf = b"# caf\xff\n@attribute series_name string\n@attribute start_timestamp date\n@frequency hourly\n@data\na:2020-01-01 00-00-00:1\n"  # noqa: E501
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", tsf)
    ev._build_monash(root, tmp_path / "o2", {})
    assert (
        tmp_path / "o2" / "monash_pedestrian" / "wide.csv"
    ).read_text() == "timestamp,a\n2020-01-01,1.0\n"


def test_dates_are_parsed_iso_as_written_and_everything_else_day_first():
    values = pd.Series(
        [
            "2024-02-03",
            "03/02/2024",
            "2024-02-03T10:30:00",
            None,
            "garbage",
            "2024-13-45",
            "12/25/2024",
        ],
        index=[10, 11, 12, 13, 14, 15, 16],
    )
    out = ev._parse_dates(values)
    assert out.index.tolist() == [10, 11, 12, 13, 14, 15, 16]
    assert str(out.dtype) == "datetime64[ns]"
    assert out.iloc[0] == pd.Timestamp("2024-02-03") and out.iloc[1] == pd.Timestamp("2024-02-03")
    assert out.iloc[2] == pd.Timestamp("2024-02-03 10:30:00")
    assert out.iloc[3:6].isna().all()  # missing, unreadable, an impossible ISO date
    assert out.iloc[6] == pd.Timestamp(
        "2024-12-25"
    )  # day-first falls back when the day is not valid
    assert ev._parse_dates(pd.Series(["01/02/2024"])).iloc[0] == pd.Timestamp("2024-02-01")
    assert ev._parse_dates(pd.Series([], dtype=object)).empty
    only_iso = ev._parse_dates(pd.Series(["2024-02-03", "2024-03-04"]))
    assert only_iso.tolist() == [pd.Timestamp("2024-02-03"), pd.Timestamp("2024-03-04")]
    unreadable_iso = ev._parse_dates(pd.Series(["2024-99-99"]))
    assert unreadable_iso.isna().all()


def test_log_views_keep_text_values_and_missing_markers_as_they_are(tmp_path):
    root = tmp_path / "acquired"
    _w(
        tmp_path / "loghub" / "X.csv",
        "LineId,Time,Level,Content,EventId,EventTemplate\n007,NA,NA,c,E1,t\n",
    )
    for n in range(3):
        out = tmp_path / f"o{n}" / "deep"  # a fresh, not yet existing output directory each time
        ev._build_loghub(root, out, {})
    text = (tmp_path / "o2" / "deep" / "loghub" / "X.csv").read_text()
    assert text == "LineId,Time,Level,EventId\n007,NA,NA,E1\n"  # not 7, not an empty cell


def test_monash_puts_the_research_directory_first_on_the_import_path(tmp_path, monkeypatch):
    import sys
    import zipfile
    from pathlib import Path

    root = tmp_path / "acquired"
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", "@attribute n s\n@frequency daily\n@data\n")
    before = list(sys.path)
    ev._build_monash(root, tmp_path / "o", {})
    assert sys.path[0] == str(Path(ev.__file__).resolve().parent) and sys.path[1:] == before
    sys.path[:] = before


def test_the_stack_builder_runs_the_extractor_with_the_documented_command(tmp_path, monkeypatch):
    import subprocess

    root = tmp_path / "acquired"
    dump = root / "stackexchange_dump" / SNAP / "raw"
    dump.mkdir(parents=True)
    (dump / "abc.stackexchange.com.7z").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, check: calls.append((command, check)))
    ev._build_stack(root, tmp_path / "o" / "deep", {})
    ((command, check),) = calls
    assert command[:3] == ["bsdtar", "-xf", str(dump / "abc.stackexchange.com.7z")]
    assert command[3] == "-C" and check is True and len(command) == 5
    assert (tmp_path / "o" / "deep" / "stackexchange" / "abc").is_dir()


def test_main_has_repository_defaults_a_description_and_path_options(tmp_path, monkeypatch, capsys):
    import json
    from pathlib import Path

    seen = {}

    def fake_build(root, out):
        seen.update(root=root, out=out)
        return {"v": {"files": {"a": {"rows": 2}}}}

    monkeypatch.setattr(ev, "build", fake_build)
    fake = tmp_path / "repo" / "research" / "experimental_views.py"
    fake.parent.mkdir(parents=True)
    default_manifest = tmp_path / "repo" / "verification" / "evidence" / "dataset_registry_v2"
    default_manifest.mkdir(parents=True)
    monkeypatch.setattr(ev, "__file__", str(fake))
    assert ev.main([]) == 0
    assert seen["root"] == tmp_path / "repo" / "data" / "acquired"
    assert seen["out"] == tmp_path / "repo" / "data" / "experimental"
    written = default_manifest / "experimental_views.json"
    assert json.loads(written.read_text()) == {"v": {"files": {"a": {"rows": 2}}}}
    assert capsys.readouterr().out.strip() == "{'v': 2}"
    assert (
        ev.main(
            [
                "--root",
                str(tmp_path / "r"),
                "--out",
                str(tmp_path / "o"),
                "--manifest",
                str(tmp_path / "m.json"),
            ]
        )
        == 0
    )
    assert isinstance(seen["root"], Path) and isinstance(seen["out"], Path)
    assert seen["root"] == tmp_path / "r" and (tmp_path / "m.json").exists()
    with pytest.raises(SystemExit):
        ev.main(["--help"])
    assert "Experimental views of acquired data" in capsys.readouterr().out


# --- HPC job records (CC-IN2P3) -----------------------------------------------------------------


def _jobs(n=6):
    return pd.DataFrame(
        {
            "jobid": [str(100 + i) for i in range(n)],
            "state": ["completed", "failed", "timeout", "cancelled", "completed", "node_fail"][:n],
            "account": [f"account{i % 2:03d}" for i in range(n)],
            "user": [f"user{i:04d}" for i in range(n)],
            "partition": ["htc", "gpu"] * (n // 2),
            "submit": [str(1000 + 10 * (n - i)) for i in range(n)],  # newest id first
            "eligible": ["1"] * n,
            "start": [str(1100 + 10 * (n - i)) if i != 1 else "" for i in range(n)],
            "end": [str(1200 + 10 * (n - i)) for i in range(n)],
            "timelimit": ["60"] * n,
            "elapsed": ["100"] * n,
            "allocmem": ["2000"] * n,
            "maxrss": ["5"] * n,
            "alloccpus": ["1"] * n,
            "totalcpu": ["9"] * n,
            "allocgpus": ["0"] * n,
            "started": ["1"] * n,
            "maxdiskwrite": ["2"] * n,
            "nsteps": ["1"] * n,
            "el9": ["0"] * n,
            "hostnames": ["b009"] * n,
        }
    )


def test_job_views_keep_the_scheduler_columns_drop_hosts_and_derive_the_waiting_time():
    out = ev.slurm_view(_jobs(), keep_modulo=1)
    assert list(out.columns) == list(ev.SLURM_COLUMNS)
    assert ev.SLURM_COLUMNS == (
        "jobid", "state", "account", "user", "partition", "submit", "start", "end", "timelimit",
        "elapsed", "allocmem", "alloccpus", "allocgpus", "wait_s",
    )  # fmt: skip
    assert out["jobid"].tolist() == ["105", "104", "103", "102", "101", "100"]  # by submit time
    assert out["submit"].tolist() == [1010, 1020, 1030, 1040, 1050, 1060]
    assert out["wait_s"].isna().tolist() == [False, False, False, False, True, False]
    assert out.loc[out["jobid"] == "100", "wait_s"].iloc[0] == 100.0
    assert "hostnames" not in out and "maxrss" not in out and "eligible" not in out
    assert (
        out["state"].tolist()[0] == "node_fail"
    )  # failures stay visible as the scheduler wrote them
    assert out["user"].tolist()[0] == "user0005"  # the producer's own pseudonym, not re-hashed


def test_job_sampling_keeps_every_nth_job_id_and_tolerates_missing_times():
    frame = _jobs()
    assert ev.slurm_view(frame, keep_modulo=2)["jobid"].tolist() == ["104", "102", "100"]
    assert ev.slurm_view(frame)["jobid"].tolist() == ["100"] and ev.SLURM_MODULO == 20
    assert ev.slurm_view(frame.iloc[0:0], keep_modulo=1).empty
    with pytest.raises(ev.ViewError, match="job columns"):
        ev.slurm_view(pd.DataFrame({"x": [1]}))


def test_the_job_builder_reads_each_month_from_its_archive_and_writes_one_sorted_table(
    tmp_path, monkeypatch
):
    import io
    import tarfile

    root = tmp_path / "acquired"
    raw = root / "slurm_ccin2p3" / SNAP / "raw"
    raw.mkdir(parents=True)
    for name, frame in (
        ("12.tsv.tar.gz", _jobs().assign(jobid=lambda f: f["jobid"].astype(int) + 100)),
        ("07.tsv.tar.gz", _jobs()),
    ):
        data = frame.to_csv(sep="\t", index=False).encode()
        with tarfile.open(raw / name, "w:gz") as tar:
            info = tarfile.TarInfo(name.replace(".tar.gz", ""))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(ev, "SLURM_MODULO", 1)
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_slurm(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "slurm_ccin2p3" / "jobs.csv"
    table = pd.read_csv(target, dtype=str)
    assert len(table) == 12 and list(table.columns) == list(ev.SLURM_COLUMNS)
    assert table["submit"].astype(int).is_monotonic_increasing
    assert manifest["slurm_ccin2p3"]["files"] == {"jobs.csv": {"sha256": _sha(target), "rows": 12}}
    assert {k: v for k, v in manifest["slurm_ccin2p3"].items() if k != "files"} == {
        "dropped": [
            "hostnames",
            "eligible",
            "maxrss",
            "totalcpu",
            "started",
            "maxdiskwrite",
            "nsteps",
            "el9",
        ],
        "pseudonymised": [],
        "sampling": "jobs with job id % 1 == 0, by submit time",
        "source_snapshot": "slurm_ccin2p3/2026-11-21",
        "notes": "user and account names are the producer's pseudonyms",
    }
    for month in ("07", "12"):
        assert f"acquired/slurm_ccin2p3/2026-11-21/raw/{month}.tsv.tar.gz" in seen
    assert [s.__name__ for s in ev.BUILD_STEPS].count("_build_slurm") == 1
