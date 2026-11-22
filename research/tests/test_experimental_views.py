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
    _w(
        root / "clinicaltrials_v2" / SNAP / "raw" / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}]}),
    )
    _w(
        root / "crossref_works" / SNAP / "raw" / "sample_00.json",
        json.dumps({"message": {"items": [{"DOI": "10.1/a"}]}}),
    )
    import gzip as _gzip

    borg = root / "google_cluster_2019a" / SNAP / "raw"
    borg.mkdir(parents=True)
    (borg / "collection_events_head.json.gz").write_bytes(
        _gzip.compress((_collection_line(1, 1, 0) + "\n").encode())
    )
    (borg / "instance_events_head.json.gz").write_bytes(
        _gzip.compress((_instance_line(1, 0, 1, 0) + "\n").encode())
    )
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
    monkeypatch.setattr(
        ev, "SERIES_SPECS", {"uci:5": {"dir": "pool", "time": ["t"], "format": "%Y-%m-%d"}}
    )
    _w(tmp_path / "pool" / "5.csv", "t,v\n2020-01-01,1\n")
    _w(root / "zen_p" / SNAP / "raw" / "p.csv", "d,k,v\n2020-01-01,a,1\n")
    monkeypatch.setattr(
        ev,
        "PANEL_SPECS",
        {
            "p": {
                "source": "zen_p",
                "file": "p.csv",
                "sep": ",",
                "time": ["d"],
                "format": "%Y-%m-%d",
                "keys": ["k"],
            }
        },
    )
    _w(root / "zen_t" / SNAP / "raw" / "a.csv", "k\tv\n1\t2\n")
    monkeypatch.setattr(
        ev,
        "TABLE_SETS",
        {"zen_t": {"dropped": [], "tables": {"a": {"keep": ["k"]}}, "relations": []}},
    )
    import zipfile as _zf

    import pyarrow as _pa
    import pyarrow.parquet as _pq

    surf = root / "zen_surf_lisa_slurm" / SNAP / "raw"
    surf.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_surf_frame(), preserve_index=False), tmp_path / "s.parquet"
    )
    with _zf.ZipFile(surf / "slurm_table_cleaned.zip", "w") as _z:
        _z.write(tmp_path / "s.parquet", "d.parquet/part-00001-x.parquet")
    fz = root / "zen_fdata_fugaku" / SNAP / "raw"
    fz.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_fdata_frame(), preserve_index=False), fz / "21_04.parquet"
    )
    mz = root / "zen_metropt2" / SNAP / "raw"
    mz.mkdir(parents=True)
    (mz / "MetroPT2_head.csv").write_bytes(b"timestamp,TP2\n2022-04-28 12:33:29.120,1.0\n")
    import gzip as _g

    ol = root / "openlibrary_dump" / SNAP / "raw"
    ol.mkdir(parents=True)
    (ol / "editions_head.txt.gz").write_bytes(_g.compress((_ol_line(1) + "\n").encode()))
    import zipfile as _zz

    ag = root / "zen_aegis_vehicle" / SNAP / "raw"
    ag.mkdir(parents=True)
    with _zz.ZipFile(ag / "Automotive-ResearchDataSet-VIF-AEGIS.zip", "w") as _a:
        _a.writestr(
            "obdData.csv",
            '"obdData_id","trip_id","obdPid","data","timestamp"\n"1","3","0C","9","2017-01-19 16:19:03.0"\n',  # noqa: E501
        )
    import zipfile as _zc

    cl = root / "zen_clue_lds" / SNAP / "raw"
    cl.mkdir(parents=True)
    with _zc.ZipFile(cl / "clue_head.zip", "w", _zc.ZIP_DEFLATED) as _c:
        _c.writestr("clue.json", _clue(1) + "\n")
    monkeypatch.setattr(ev, "XES_SPECS", {})
    monkeypatch.setattr(ev, "CSV_EVENT_SPECS", {})
    _fs = tmp_path / "flat_sel.json"
    _fs.write_text('{"views": []}')
    monkeypatch.setattr(ev, "FLAT_SELECTION", _fs)
    _w(root / "met_museum_objects" / SNAP / "raw" / "obj_1.json", '{"objectID": 1}')
    import gzip as _gz

    dv = root / "dgfip_dvf" / SNAP / "raw"
    dv.mkdir(parents=True)
    (dv / "dvf_69_2024.csv.gz").write_bytes(_gz.compress(_dvf_frame().to_csv(index=False).encode()))
    _w(root / "hmlr_price_paid" / SNAP / "raw" / "pp-2024_head.csv", PPD_HEAD)
    (tmp_path / "uci_wave2").mkdir(exist_ok=True)
    _retail_frame().to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    import pyarrow as _pa
    import pyarrow.parquet as _pq

    pb = root / "zen_pbdb" / SNAP / "raw"
    pb.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_pbdb_frame(), preserve_index=False), tmp_path / "pb.parquet"
    )
    with _zc.ZipFile(pb / "pbdb_parquet.zip", "w") as _p:
        _p.write(tmp_path / "pb.parquet", "pbdb_occs.parquet")
    km = root / "zen_kelmarsh" / SNAP / "raw"
    km.mkdir(parents=True)
    _kelmarsh_zip(km / "Kelmarsh_SCADA_2016_3082.zip")
    _w(
        root / "wikidata_entities" / SNAP / "raw" / "entities_00.json",
        json.dumps({"entities": {"Q1": {"id": "Q1", "claims": {}}}}),
    )
    import pyarrow.feather as _fe2

    bs = root / "zen_bess" / SNAP / "raw"
    bs.mkdir(parents=True)
    _fe2.write_feather(_pa.Table.from_pandas(_bess_frame(), preserve_index=False), bs / "S.feather")
    _care_snapshot(root, ids=(1,))
    _maude_snapshot(root)
    _tlc_page([{}]).to_csv(_tlc_dir(root), index=False)
    _aqs_snapshot(root)
    _usgs_snapshot(root)
    _wiki_snapshot(root)
    _uniprot_snapshot(root)
    _osv_snapshot(root)
    _gfz_snapshot(root)
    _dwd_snapshot(root)
    _rte_snapshot(root)
    _ademe_snapshot(root)
    _alim_snapshot(root)
    _ev_snapshot(root)
    _azure_snapshot(root)
    _aoe_snapshot(root)
    _charity_snapshot(root)
    _japan_snapshot(root)
    _coops_snapshot(root)
    _gml_co2_snapshot(root)
    _cnc_snapshot(root)
    _wb_snapshot(root)
    _qld_snapshot(root)
    _inpi_snapshot(root)
    _ror_snapshot(root)
    _rcsb_snapshot(root)
    _nws_snapshot(root)
    _bb_zip(root)
    _pbdb_rel_snapshot_extra(root, tmp_path)
    _care_a_snapshot(root)
    _w(root / "nvd_cve" / ev.NVD_SNAPSHOT / "raw" / "cves_a.json", json.dumps(_nvd_page(["CVE-1"])))
    _unisg_snapshot(root)
    monkeypatch.setattr(ev, "EA_STATIONS", ["s"])
    _w(
        root / "ea_hydrology_flow" / SNAP / "raw" / "flow_s.csv",
        "date,value,completeness\n2020-01-01,1,Complete\n",
    )
    out = tmp_path / "out"
    manifest = ev.build(root, out)
    assert list(manifest) == [
        "openalex", "monash_pedestrian", "openfda_drug_event", "loghub", "openfoodfacts", "stackexchange",  # noqa: E501
        "ocds_montreal", "ocds_georgia", "ocds_zambia", "bikeshare_capital", "bikeshare_jc",
        "slurm_ccin2p3", "clinicaltrials_v2", "crossref_works", "google_cluster_2019a", "panels", "zen_t", "zen_surf_lisa_slurm", "zen_fdata_fugaku", "zen_metropt2", "openlibrary_dump", "zen_aegis_vehicle", "zen_clue_lds", "met_museum_objects", "ea_hydrology_flow", "dgfip_dvf", "hmlr_price_paid", "uci_online_retail", "zen_pbdb", "zen_pbdb_relational", "zen_kelmarsh", "wikidata_entities", "zen_bess", "zen_care_wind_b", "zen_care_wind_a", "nvd_cve", "zen_unisg_factory", "backblaze_drive_stats", "nyc_tlc_yellow", "openfda_device_event", "epa_aqs_ozone_hourly", "usgs_continuous_discharge", "wikimedia_simplewiki_edits", "uniprot_kb_reviewed", "osv_go_advisories", "gfz_kp_index", "dwd_hourly_climate", "rte_eco2mix_national", "ademe_dpe_existant", "dgal_alimconfiance", "zen_ev_charging", "azure_packing_2020", "zen_aoe_interactions", "uk_charity_register", "zen_japan_buildings", "noaa_coops_tides", "noaa_gml_co2_weekly", "zen_cnc_milling", "wb_lending_projects", "zen_queensland_petrol", "inpi_bce_ratios", "ror_organizations", "rcsb_pdb_entries", "nws_weather_alerts", "series", "ukspend",  # noqa: E501
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


def test_the_research_directory_is_on_the_import_path_once_and_the_monash_builder_runs(tmp_path):
    import sys
    import zipfile
    from pathlib import Path

    here = str(Path(ev.__file__).resolve().parent)
    assert here in sys.path and str(ev._HERE) == here  # sibling modules import by name
    root = tmp_path / "acquired"
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", "@attribute n s\n@frequency daily\n@data\n")
    before = list(sys.path)
    manifest: dict = {}
    ev._build_monash(root, tmp_path / "o", manifest)
    assert (
        sys.path == before and "monash_pedestrian" in manifest
    )  # a builder no longer edits the path


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


# --- generic nested views: clinical-trial records and bibliographic metadata ---------------------


def test_nested_views_drop_the_named_keys_at_every_depth_sort_and_do_not_modify_the_input():
    records = [
        {"id": "b", "x": {"name": "n", "keep": [{"name": "m", "k": 1}]}, "name": "top"},
        {"id": "a", "x": {"keep": []}},
    ]
    out = ev.nested_view(records, drop=frozenset(["name"]), key=lambda r: r["id"])
    assert out == [{"id": "a", "x": {"keep": []}}, {"id": "b", "x": {"keep": [{"k": 1}]}}]
    assert records[0]["name"] == "top" and records[0]["x"]["keep"][0]["name"] == "m"
    assert ev.nested_view([], drop=frozenset(), key=lambda r: 0) == []


def test_clinical_trial_views_remove_people_and_contact_details_but_keep_the_trial_structure():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT2", "organization": {"fullName": "Org A"}},
            "contactsLocationsModule": {
                "centralContacts": [{"name": "Ann", "email": "a@b"}],
                "overallOfficials": [{"name": "Bob", "affiliation": "U"}],
                "locations": [{"city": "Paris", "contacts": [{"name": "Cy", "phone": "1"}]}],
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Sponsor Inc", "class": "INDUSTRY"},
                "responsibleParty": {
                    "type": "PI",
                    "investigatorFullName": "Dee",
                    "investigatorTitle": "Dr",
                },
            },
        },
        "resultsSection": {"moreInfoModule": {"pointOfContact": {"email": "x@y"}}},
    }
    other = {"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}
    out = ev.clinical_trials_view([study, other])
    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in out] == ["NCT1", "NCT2"]
    text = json.dumps(out)
    for word in (
        "Ann",
        "a@b",
        "Bob",
        "Cy",
        "Dee",
        "x@y",
        "centralContacts",
        "overallOfficials",
        "pointOfContact",
    ):
        assert word not in text
    kept = out[1]["protocolSection"]
    assert kept["contactsLocationsModule"]["locations"] == [{"city": "Paris"}]
    assert kept["sponsorCollaboratorsModule"]["leadSponsor"] == {
        "name": "Sponsor Inc",
        "class": "INDUSTRY",
    }
    assert kept["sponsorCollaboratorsModule"]["responsibleParty"] == {"type": "PI"}
    assert kept["identificationModule"]["organization"] == {"fullName": "Org A"}
    assert frozenset(
        ["centralContacts", "overallOfficials", "pointOfContact", "contacts", "investigatorFullName",  # noqa: E501
         "investigatorTitle", "investigatorAffiliation"]
    ) == ev.CT_DROP  # fmt: skip


def test_bibliographic_views_replace_authors_by_their_count_and_sort_by_doi_without_duplicates():
    works = [
        {
            "DOI": "10.2/b",
            "title": ["T"],
            "author": [{"name": "Ann", "ORCID": "o"}, {"name": "Bo"}],
            "reference": [{"DOI": "x"}],
        },
        {"DOI": "10.1/a", "title": ["U"]},
        {"DOI": "10.2/b", "title": ["T again"], "author": []},
    ]
    out = ev.crossref_view(works)
    assert [w["DOI"] for w in out] == ["10.1/a", "10.2/b"]  # one record per DOI
    assert out[0] == {"DOI": "10.1/a", "title": ["U"], "n_authors": 0}
    assert (
        out[1]["n_authors"] == 2
        and "author" not in out[1]
        and out[1]["reference"] == [{"DOI": "x"}]
    )
    assert "Ann" not in json.dumps(out) and "ORCID" not in json.dumps(out)


def test_the_study_and_bibliography_builders_write_sorted_json_lines_and_manifests(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    ct = root / "clinicaltrials_v2" / SNAP / "raw"
    _w(
        ct / "studies_2023-02.json",
        json.dumps(
            {
                "studies": [
                    {"protocolSection": {"identificationModule": {"nctId": "NCT2"}, "z": 1, "a": 2}}
                ]
            }
        ),
    )
    _w(
        ct / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}]}),
    )
    cr = root / "crossref_works" / SNAP / "raw"
    _w(
        cr / "sample_01.json",
        json.dumps({"message": {"items": [{"DOI": "10.9/z", "author": [{"name": "A"}]}]}}),
    )
    _w(
        cr / "sample_00.json",
        json.dumps({"message": {"items": [{"DOI": "10.1/a"}, {"DOI": "10.9/z"}]}}),
    )
    seen = _accessed(monkeypatch, root)
    manifest = {}
    out = tmp_path / "o" / "deep"
    ev._build_clinicaltrials(root, out, manifest)
    ev._build_crossref(root, out, manifest)
    lines = (out / "clinicaltrials_v2" / "studies.jsonl").read_text().splitlines()
    assert [json.loads(x)["protocolSection"]["identificationModule"]["nctId"] for x in lines] == [
        "NCT1",
        "NCT2",
    ]
    assert (
        lines[1]
        == '{"protocolSection": {"a": 2, "identificationModule": {"nctId": "NCT2"}, "z": 1}}'
    )
    dois = [
        json.loads(x)["DOI"]
        for x in (out / "crossref_works" / "works.jsonl").read_text().splitlines()
    ]
    assert dois == ["10.1/a", "10.9/z"]
    assert manifest["clinicaltrials_v2"]["files"] == {
        "studies.jsonl": {"sha256": _sha(out / "clinicaltrials_v2" / "studies.jsonl"), "rows": 2}
    }
    assert {k: v for k, v in manifest["clinicaltrials_v2"].items() if k != "files"} == {
        "dropped": sorted(ev.CT_DROP), "pseudonymised": [], "source_snapshot": "clinicaltrials_v2/2026-11-21",  # noqa: E501
    }  # fmt: skip
    assert manifest["crossref_works"]["files"]["works.jsonl"]["rows"] == 2
    assert {k: v for k, v in manifest["crossref_works"].items() if k != "files"} == {
        "dropped": ["author"], "pseudonymised": [], "source_snapshot": "crossref_works/2026-11-21",
        "notes": "authors are replaced by their count; one record per DOI",
    }  # fmt: skip
    assert "acquired/clinicaltrials_v2/2026-11-21/raw/studies_2023-01.json" in seen
    assert "acquired/crossref_works/2026-11-21/raw/sample_01.json" in seen


def test_email_addresses_in_free_text_are_redacted_at_every_depth_without_touching_other_text():
    node = {
        "a": "write to Jo.Doe+x@lab-1.example.co.uk or sam@x.org now",
        "b": [{"c": "no address, 3 @ 4"}, "plain@host"],
        "d": 5,
        "e": None,
        "f": {"g": "a@b.cd"},
    }
    assert ev.redact_emails(node) == {
        "a": "write to [email] or [email] now",
        "b": [{"c": "no address, 3 @ 4"}, "plain@host"],
        "d": 5,
        "e": None,
        "f": {"g": "[email]"},
    }
    assert node["a"].startswith("write to Jo.Doe")  # the input is not modified


def test_study_views_also_redact_addresses_written_in_data_sharing_statements():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "N"},
            "ipdSharingStatementModule": {"description": "ask me@uni.edu"},
        }
    }
    out = ev.clinical_trials_view([study])
    assert out[0]["protocolSection"]["ipdSharingStatementModule"]["description"] == "ask [email]"


# --- time-series tables with a verified time column ---------------------------------------------


def test_series_views_parse_the_declared_format_drop_unreadable_times_and_keep_numeric_columns():
    raw = pd.DataFrame(
        {
            "Date": ["3/10/2004", "3/11/2004", "13/45/2004", "3/10/2004"],
            "Time": ["18:00:00", "19:00:00", "00:00:00", "17:00:00"],
            "CO": ["2.6", "2", "9", "x"],
            "label": ["a", "b", "c", "d"],
        }
    )
    spec = {"time": ["Date", "Time"], "format": "%m/%d/%Y %H:%M:%S"}
    out = ev.series_view(raw, spec)
    assert list(out.columns) == ["timestamp", "CO"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2004-03-10 17:00:00"),
        pd.Timestamp("2004-03-10 18:00:00"),
        pd.Timestamp("2004-03-11 19:00:00"),
    ]
    assert out["CO"].isna().tolist() == [True, False, False]  # an unreadable value stays missing
    assert out["CO"].iloc[1] == 2.6
    assert out.attrs == {"rows_dropped": 1}
    assert len(raw) == 4


def test_series_views_add_an_hour_column_and_handle_a_single_time_column():
    raw = pd.DataFrame(
        {"Date": ["1/12/2017", "1/12/2017"], "Hour": ["1", "0"], "Rented": ["10", "5"]}
    )
    spec = {"time": ["Date"], "format": "%d/%m/%Y", "hour": "Hour"}
    out = ev.series_view(raw, spec)
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2017-12-01 00:00"),
        pd.Timestamp("2017-12-01 01:00"),
    ]
    assert list(out.columns) == ["timestamp", "Rented"] and out["Rented"].tolist() == [5.0, 10.0]
    iso = pd.DataFrame(
        {"t": ["2019-11-06 11:37:13+01:00", "2019-11-06 11:37:12+01:00"], "v": ["1", "2"]}
    )
    parsed = ev.series_view(iso, {"time": ["t"], "format": "ISO8601"})
    assert parsed["v"].tolist() == [2.0, 1.0] and str(parsed["timestamp"].dtype).startswith(
        "datetime64"
    )
    bom = pd.DataFrame({"﻿date": ["01/01/2018 00:15"], "k": ["3"]})
    assert ev.series_view(bom, {"time": ["date"], "format": "%d/%m/%Y %H:%M"})["k"].tolist() == [
        3.0
    ]
    with pytest.raises(ev.ViewError, match="time column"):
        ev.series_view(raw, {"time": ["nope"], "format": "%d/%m/%Y"})


def test_the_series_builder_reads_pool_and_wave2_tables_and_writes_sorted_views(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    root.mkdir()
    specs = {
        "uci:5": {"dir": "pool", "time": ["date"], "format": "%Y-%m-%d %H:%M:%S"},
        "uci:6": {"dir": "uci_wave2", "time": ["d"], "format": "%m/%d/%Y"},
    }
    monkeypatch.setattr(ev, "SERIES_SPECS", specs)
    _w(tmp_path / "pool" / "5.csv", "id,date,v\n1,2015-02-04 17:52:00,2\n2,2015-02-04 17:51:00,1\n")
    _w(tmp_path / "uci_wave2" / "6.csv", "d,w\n1/2/1998,3\n1/1/1998,4\n")
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_series(root, tmp_path / "o" / "deep", manifest)
    assert (
        tmp_path / "o" / "deep" / "series" / "uci_5.csv"
    ).read_text() == "timestamp,id,v\n2015-02-04 17:51:00,2,1\n2015-02-04 17:52:00,1,2\n"
    assert (
        tmp_path / "o" / "deep" / "series" / "uci_6.csv"
    ).read_text() == "timestamp,w\n1998-01-01,4\n1998-01-02,3\n"
    assert list(manifest["series"]["files"]) == ["uci_5.csv", "uci_6.csv"]
    assert manifest["series"]["files"]["uci_5.csv"] == {
        "sha256": _sha(tmp_path / "o" / "deep" / "series" / "uci_5.csv"),
        "rows": 2,
    }
    assert manifest["series"]["dropped"] == []
    assert (
        manifest["series"]["source_snapshot"]
        == "data/pool and data/uci_wave2 tables, pinned by the pool manifests"
    )
    assert manifest["series"]["rows_dropped"] == {"uci:5": 0, "uci:6": 0}
    assert "pool/5.csv" in seen and "uci_wave2/6.csv" in seen
    assert set(ev.SERIES_SPECS) == set(specs)


def test_the_new_builders_create_missing_parents_twice_and_write_exact_paths_and_sorted_keys(
    tmp_path, monkeypatch
):
    import builtins
    import io

    root = tmp_path / "acquired"
    ct = root / "clinicaltrials_v2" / SNAP / "raw"
    _w(
        ct / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "N1"}}}]}),
    )
    cr = root / "crossref_works" / SNAP / "raw"
    _w(
        cr / "sample_00.json",
        json.dumps(
            {"message": {"items": [{"title": ["t"], "DOI": "10.1/a", "author": [{"name": "A"}]}]}}
        ),
    )
    _w(tmp_path / "pool" / "5.csv", "t,v\n2020-01-01,1\n")
    monkeypatch.setattr(
        ev, "SERIES_SPECS", {"uci:5": {"dir": "pool", "time": ["t"], "format": "%Y-%m-%d"}}
    )
    out = tmp_path / "o" / "deep"
    written = []
    real_open = builtins.open

    def spy(file, mode="r", *a, **k):
        if "w" in mode and str(file).startswith(str(out)):
            written.append(str(file)[len(str(out)) + 1 :])
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    for step in (ev._build_clinicaltrials, ev._build_crossref, ev._build_series):
        manifest = {}
        step(root, out, manifest)
        step(root, out, manifest)  # a second run over existing directories
    assert sorted(set(written)) == [
        "clinicaltrials_v2/studies.jsonl",
        "crossref_works/works.jsonl",
        "series/uci_5.csv",
    ]
    text = (out / "crossref_works" / "works.jsonl").read_text()
    assert text == '{"DOI": "10.1/a", "n_authors": 1, "title": ["t"]}\n'  # keys in sorted order


def test_series_edge_cases_stable_order_unreadable_hours_and_the_error_message():
    raw = pd.DataFrame(
        {
            "t": ["2020-01-01", "2020-01-01", "2020-01-01"],
            "k": ["a", "b", "c"],
            "v": ["3", "1", "2"],
        }
    )
    out = ev.series_view(raw, {"time": ["t"], "format": "%Y-%m-%d"})
    assert out["v"].tolist() == [3.0, 1.0, 2.0]  # equal timestamps keep their file order
    hours = pd.DataFrame({"d": ["01/01/2020", "01/01/2020"], "h": ["x", "2"], "v": ["1", "2"]})
    parsed = ev.series_view(hours, {"time": ["d"], "format": "%d/%m/%Y", "hour": "h"})
    assert parsed["v"].tolist() == [2.0] and parsed.attrs["rows_dropped"] == 1
    wide = pd.DataFrame({f"c{i}": [1] for i in range(8)})
    with pytest.raises(ev.ViewError) as info:
        ev.series_view(wide, {"time": ["missing"], "format": "%Y"})
    assert str(info.value) == "time column not found in ['c0', 'c1', 'c2', 'c3', 'c4', 'c5']"
    assert set(ev.SERIES_SPECS) == {
        "uci:357",
        "uci:360",
        "uci:374",
        "uci:560",
        "uci:799",
        "uci:849",
        "uci:851",
        "uci:172",
        "uci:492",
    }


# --- Borg cluster trace prefixes (event sequences) -----------------------------------------------


def _collection_line(cid, time, kind, **over):
    record = {
        "time": str(time), "type": str(kind), "collection_id": str(cid), "scheduling_class": "1",
        "collection_type": "0", "priority": "103", "user": "HASHED=", "collection_name": "HASHED2=",
        "collection_logical_name": "HASHED3=", "start_after_collection_ids": [], "vertical_scaling": "2",  # noqa: E501
        "scheduler": "1",
    }  # fmt: skip
    record.update(over)
    return json.dumps(record)


def _instance_line(cid, index, time, kind, machine="9"):
    return json.dumps(
        {"time": str(time), "type": str(kind), "collection_id": str(cid), "scheduling_class": "0",
         "collection_type": "0", "priority": "114", "instance_index": str(index), "machine_id": machine,  # noqa: E501
         "alloc_collection_id": "0", "alloc_instance_index": "-1", "missing_type": "1",
         "resource_request": {"cpus": 0.5, "memory": 0.25}, "constraint": []}
    )  # fmt: skip


def test_collection_event_views_keep_the_sequence_fields_drop_hashed_names_and_order_each_collection():  # noqa: E501
    lines = [
        _collection_line(2, 30, 6),
        _collection_line(1, 20, 3),
        _collection_line(1, 10, 0),
        "",
        _collection_line(2, 5, 0),
    ]
    out = ev.borg_collection_view(lines)
    assert list(out.columns) == list(ev.BORG_COLLECTION_COLUMNS)
    assert ev.BORG_COLLECTION_COLUMNS == (
        "collection_id", "time_us", "type", "collection_type", "priority", "scheduling_class",
        "scheduler", "vertical_scaling",
    )  # fmt: skip
    assert out["collection_id"].tolist() == [1, 1, 2, 2]
    assert out["time_us"].tolist() == [10, 20, 5, 30]  # time order inside each collection
    assert out["type"].tolist() == [0, 3, 0, 6]
    assert out.iloc[0].to_dict() == {
        "collection_id": 1,
        "time_us": 10,
        "type": 0,
        "collection_type": 0,
        "priority": 103,
        "scheduling_class": 1,
        "scheduler": 1,
        "vertical_scaling": 2,
    }
    assert "user" not in out and "collection_name" not in out
    assert len(ev.borg_collection_view([])) == 0
    missing = json.dumps({"time": "1", "type": "0", "collection_id": "7"})
    assert pd.isna(ev.borg_collection_view([missing])["priority"].iloc[0])


def test_instance_event_views_unpack_the_resource_request_and_order_each_instance():
    lines = [
        _instance_line(1, 1, 50, 6),
        _instance_line(1, 0, 40, 3),
        _instance_line(1, 1, 10, 0, machine=""),
    ]
    out = ev.borg_instance_view(lines)
    assert list(out.columns) == list(ev.BORG_INSTANCE_COLUMNS)
    assert out[["collection_id", "instance_index", "time_us", "type"]].values.tolist() == [
        [1, 0, 40, 3],
        [1, 1, 10, 0],
        [1, 1, 50, 6],
    ]
    assert out["cpus"].tolist() == [0.5, 0.5, 0.5] and out["memory"].tolist() == [0.25, 0.25, 0.25]
    assert out["machine_id"].tolist()[0] == 9 and pd.isna(out["machine_id"].iloc[1])
    bare = json.dumps({"time": "1", "type": "0", "collection_id": "1", "instance_index": "0"})
    row = ev.borg_instance_view([bare]).iloc[0]
    assert pd.isna(row["cpus"]) and pd.isna(row["memory"])


def test_the_borg_builder_reads_gzip_prefixes_records_the_cut_and_caps_the_rows(
    tmp_path, monkeypatch
):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "google_cluster_2019a" / SNAP / "raw"
    raw.mkdir(parents=True)
    text = "\n".join(_collection_line(i % 7, 100 - i, i % 4) for i in range(60)) + "\n"
    blob = gzip.compress(text.encode())
    (raw / "collection_events_head.json.gz").write_bytes(blob[: len(blob) * 3 // 4])  # a cut stream
    text = "\n".join(_instance_line(i % 3, i % 5, 100 - i, i % 4) for i in range(40)) + "\n"
    (raw / "instance_events_head.json.gz").write_bytes(gzip.compress(text.encode()))
    monkeypatch.setattr(ev, "BORG_MAX_LINES", 25)
    manifest = {}
    ev._build_borg(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "google_cluster_2019a"
    assert len(pd.read_csv(folder / "collection_events.csv")) == 25  # capped, a prefix of the file
    assert len(pd.read_csv(folder / "instance_events.csv")) == 25
    view = manifest["google_cluster_2019a"]
    assert view["files"] == {
        "collection_events.csv": {"sha256": _sha(folder / "collection_events.csv"), "rows": 25},
        "instance_events.csv": {"sha256": _sha(folder / "instance_events.csv"), "rows": 25},
    }
    assert view["sampling"].startswith("prefix of one shard in file order")
    assert view["fragments"]["collection_events_head.json.gz"]["stream_complete"] is False
    assert view["fragments"]["instance_events_head.json.gz"]["stream_complete"] is True
    assert view["fragments"]["instance_events_head.json.gz"]["lines_read"] == 40
    assert {k: v for k, v in view.items() if k not in ("files", "fragments", "sampling")} == {
        "dropped": [
            "user",
            "collection_name",
            "collection_logical_name",
            "constraint",
            "alloc fields",
        ],
        "pseudonymised": [],
        "source_snapshot": "google_cluster_2019a/2026-11-21",
    }


# --- panels of series (RKI) and multi-table relational extracts (3PFL) ---------------------------


def test_panel_views_keep_key_columns_sort_by_key_then_time_and_read_na_markers_as_missing():
    raw = pd.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-01", "2020-01-01", "bad"],
            "region": ["B", "B", "A", "A"],
            "cases": ["5", "NA", "3", "9"],
            "note": ["x", "y", "z", "w"],
        }
    )
    spec = {"time": ["date"], "format": "%Y-%m-%d", "keys": ["region"]}
    out = ev.panel_view(raw, spec)
    assert list(out.columns) == ["timestamp", "region", "cases"]
    assert out["region"].tolist() == ["A", "B", "B"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-02"),
    ]
    assert out["cases"].isna().tolist() == [False, True, False]
    assert out.attrs == {"rows_dropped": 1}
    with pytest.raises(ev.ViewError, match="key column"):
        ev.panel_view(raw, {**spec, "keys": ["zzz"]})


def _tables():
    return {
        "01_links": pd.DataFrame({"piid": ["p1", "p2", "p9"], "patent": ["10", "11", "12"]}),
        "02_orders": pd.DataFrame(
            {"piid": ["p1", "p2"], "vendor": ["v1", "v2"], "title": ["secret a", "secret b"]}
        ),
        "03_vendors": pd.DataFrame({"vendor": ["v1"], "street": ["1 rue"], "state": ["OH"]}),
    }


TABLE_SPEC = {
    "tables": {
        "01_links": {"keep": ["piid", "patent"]},
        "02_orders": {"keep": ["piid", "vendor"]},
        "03_vendors": {"keep": ["vendor", "state"]},
    },
    "relations": [
        ["01_links", "piid", "02_orders", "piid"],
        ["02_orders", "vendor", "03_vendors", "vendor"],
        ["01_links", "piid", "02_orders", "piid", {"where": ["patent", "10"]}],
    ],
}


def test_table_views_keep_only_listed_columns_and_measure_every_relation_with_its_orphans():
    out, relations = ev.tables_view(_tables(), TABLE_SPEC)
    assert list(out) == ["01_links", "02_orders", "03_vendors"]
    assert (
        list(out["02_orders"].columns) == ["piid", "vendor"] and "street" not in out["03_vendors"]
    )
    assert relations == [
        {
            "child": "01_links.piid",
            "parent": "02_orders.piid",
            "checked": 3,
            "orphans": 1,
            "share": 1 / 3,
        },
        {
            "child": "02_orders.vendor",
            "parent": "03_vendors.vendor",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
        {
            "child": "01_links.piid where patent=10",
            "parent": "02_orders.piid",
            "checked": 1,
            "orphans": 0,
            "share": 0.0,
        },
    ]
    with pytest.raises(ev.ViewError, match="column"):
        ev.tables_view(_tables(), {"tables": {"01_links": {"keep": ["nope"]}}, "relations": []})
    with pytest.raises(ev.ViewError, match="table"):
        ev.tables_view({}, TABLE_SPEC)


def test_the_panel_and_relational_builders_write_views_and_record_relations(tmp_path, monkeypatch):
    root = tmp_path / "acquired"
    raw = root / "zen_rki_notaufnahme" / SNAP / "raw"
    _w(
        raw / "Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv",
        "date\tsyndrome\tn\n2019-01-02\tARI\t2\n2019-01-01\tARI\t1\n",
    )
    monkeypatch.setattr(
        ev,
        "PANEL_SPECS",
        {
            "rki_notaufnahme": {
                "source": "zen_rki_notaufnahme",
                "file": "Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv",
                "sep": "\t",
                "time": ["date"],
                "format": "%Y-%m-%d",
                "keys": ["syndrome"],
            }
        },
    )
    manifest = {}
    ev._build_panels(root, tmp_path / "o" / "deep", manifest)
    ev._build_panels(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "panels" / "rki_notaufnahme.csv"
    assert target.read_text() == "timestamp,syndrome,n\n2019-01-01,ARI,1\n2019-01-02,ARI,2\n"
    assert manifest["panels"]["files"] == {
        "rki_notaufnahme.csv": {"sha256": _sha(target), "rows": 2}
    }
    assert manifest["panels"]["rows_dropped"] == {"rki_notaufnahme": 0}
    tables = root / "zen_3pfl" / SNAP / "raw"
    _w(tables / "01_links.csv", 'piid\tpatent\n"p1"\t"10"\n"p9"\t"12"\n')
    _w(tables / "02_orders.csv", 'piid\tvendor\ttitle\n"p1"\t"v1"\t"s"\n')
    monkeypatch.setattr(ev, "TABLE_SETS", {"zen_3pfl": {"dropped": ["names"],
        "tables": {"01_links": {"keep": ["piid", "patent"]}, "02_orders": {"keep": ["piid", "vendor"]}},  # noqa: E501
        "relations": [["01_links", "piid", "02_orders", "piid"]]}})  # fmt: skip
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "zen_3pfl"
    assert (
        folder / "01_links.csv"
    ).read_text() == "piid,patent\np1,10\np9,12\n"  # quotes are not data
    assert (folder / "02_orders.csv").read_text() == "piid,vendor\np1,v1\n"
    view = manifest["zen_3pfl"]
    assert view["relations"] == [
        {
            "child": "01_links.piid",
            "parent": "02_orders.piid",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        }
    ]
    assert view["files"]["01_links.csv"] == {"sha256": _sha(folder / "01_links.csv"), "rows": 2}
    assert (
        view["notes"]
        == "relations are the source's own keys; orphans are natural incompleteness of the published extract"  # noqa: E501
    )


# --- SURF Lisa SLURM job table from a zipped Parquet part ----------------------------------------


def _surf_frame():
    return pd.DataFrame(
        {
            "id": pd.array([3, 1, 2], dtype="int32"),
            "start_date": pd.to_datetime(["2022-01-01 10:00:00", "2022-01-01 09:00:00", None]),
            "end_date": pd.to_datetime(["2022-01-01 10:30:00", "2022-01-01 09:10:00", None]),
            "node": ["r1n1", "r1n2", "r1n3"],
            "nodetypes": ["normal(1)", "gpu(1)", "normal(1)"],
            "numnodes": ["1", "2", "x"],
            "numcores": ["16", "32", "8"],
            "submit_date": pd.to_datetime(["2022-01-01 09:55:00", "2022-01-01 08:00:00", "2022-01-01 09:00:00"]),  # noqa: E501
            "state": ["COMPLETED", "FAILED", "CANCELLED"],
        }
    )  # fmt: skip


def test_surf_job_view_derives_wait_and_runtime_orders_by_submit_and_keeps_unstarted_jobs():
    out = ev.surf_slurm_view(_surf_frame())
    assert list(out.columns) == list(ev.SURF_COLUMNS)
    assert ev.SURF_COLUMNS == (
        "job_id", "submit_ts", "wait_s", "runtime_s", "nodes", "cores", "node_type", "state",
    )  # fmt: skip
    assert out["job_id"].tolist() == [1, 2, 3]  # submit order
    assert out["wait_s"].tolist()[0] == 3600.0 and out["runtime_s"].tolist()[0] == 600.0
    assert pd.isna(out["wait_s"].iloc[1]) and pd.isna(out["runtime_s"].iloc[1])  # never started
    assert out["wait_s"].iloc[2] == 300.0 and out["runtime_s"].iloc[2] == 1800.0
    assert out["nodes"].iloc[0] == 2 and pd.isna(
        out["nodes"].iloc[1]
    )  # unreadable count stays missing
    assert out["cores"].tolist() == [32, 8, 16]
    assert out["node_type"].tolist() == ["gpu", "normal", "normal"]
    assert out["state"].tolist() == ["FAILED", "CANCELLED", "COMPLETED"]
    assert "node" not in out  # host names are not experimental features
    with pytest.raises(ev.ViewError, match="column"):
        ev.surf_slurm_view(_surf_frame().drop(columns=["state"]))


def test_the_surf_builder_extracts_the_zipped_part_samples_with_a_stride_and_records_it(
    tmp_path, monkeypatch
):
    import zipfile

    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "acquired"
    raw = root / "zen_surf_lisa_slurm" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(
            pd.concat([_surf_frame()] * 4, ignore_index=True), preserve_index=False
        ),
        tmp_path / "p.parquet",
        row_group_size=5,
    )
    empty = tmp_path / "empty.parquet"
    pq.write_table(pa.Table.from_pandas(_surf_frame().iloc[:0], preserve_index=False), empty)
    with zipfile.ZipFile(raw / "slurm_table_cleaned.zip", "w") as z:
        z.write(empty, "slurm_table_cleaned.parquet/part-00000-x.snappy.parquet")
        z.write(tmp_path / "p.parquet", "slurm_table_cleaned.parquet/part-00003-x.snappy.parquet")
    monkeypatch.setattr(ev, "SURF_STRIDE", 3)
    manifest = {}
    ev._build_surf(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_surf_lisa_slurm" / "jobs.csv"
    assert len(pd.read_csv(target)) == 4  # rows 0, 3, 6, 9 of 12
    view = manifest["zen_surf_lisa_slurm"]
    assert view["files"] == {"jobs.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["sampling"] == {
        "method": "one row in 3 of the only non-empty Parquet part, from the first, in file order",
        "stride": 3, "rows_read": 12, "rows_kept": 4, "source_rows": 12, "truncated": False,
        "member": "slurm_table_cleaned.parquet/part-00003-x.snappy.parquet",
    }  # fmt: skip
    assert view["dropped"] == ["node host names"]


# --- Fugaku job records (Parquet) and the MetroPT2 time-ordered CSV prefix ------------------------


def _fdata_frame():
    return pd.DataFrame(
        {
            "jid": ["a", "b", "c"], "usr": ["u1", "u2", "u3"], "jnam": ["n1", "n2", "n3"],
            "cnumr": [48, 96, 48], "cnumat": [48, 96, 48], "nnumr": [1, 2, 1], "nnuma": [1, 2, 1],
            "adt": ["2021-04-02 10:00:00", "2021-04-01 09:00:00", "2021-04-03 08:00:00"],
            "sdt": ["2021-04-02 10:10:00", "2021-04-01 09:30:00", None],
            "edt": ["2021-04-02 11:10:00", "2021-04-01 09:40:00", None],
            "ec": [0, 1, 0], "elpl": [3600.0, 600.0, 60.0], "pri": [1, 2, 3],
            "econ": [5.0, 1.0, None], "avgpcon": [100.0, 90.0, None], "maxpcon": [120.0, 95.0, None],  # noqa: E501
            "mszl": [1.0, 2.0, 3.0], "msza": [1, 2, 3], "mmszu": [0.5, 1.0, None], "pclass": ["compute", "memory", None],  # noqa: E501
            "exit state": ["completed", "failed", "cancelled"], "duration": [3600.0, 600.0, None],
            "embedding": [[0.1], [0.2], [0.3]], "jobenv_req": ["x", "y", "z"],
        }
    )  # fmt: skip


def test_fugaku_job_view_drops_identifiers_and_text_derives_wait_and_orders_by_arrival():
    out = ev.fugaku_jobs_view(_fdata_frame())
    assert list(out.columns) == list(ev.FUGAKU_COLUMNS)
    assert out["submit_ts"].tolist() == sorted(out["submit_ts"].tolist())
    assert (
        out["wait_s"].iloc[0] == 1800.0
        and out["wait_s"].iloc[1] == 600.0
        and pd.isna(out["wait_s"].iloc[2])
    )
    assert out["state"].tolist() == ["failed", "completed", "cancelled"]
    for gone in ("jid", "usr", "jnam", "embedding", "jobenv_req"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column"):
        ev.fugaku_jobs_view(_fdata_frame().drop(columns=["adt"]))


def test_csv_prefixes_keep_only_complete_lines_and_say_how_many_bytes_were_cut():
    blob = b"a,b\n1,2\n3,4\n5,"
    frame, cut = ev.csv_prefix(blob)
    assert frame.to_dict("list") == {"a": [1, 3], "b": [2, 4]} and cut == 2
    whole, none = ev.csv_prefix(b"a,b\n1,2\n")
    assert len(whole) == 1 and none == 0


def test_the_metropt_view_drops_gps_columns_and_keeps_time_order_and_sensors():
    raw = pd.DataFrame(
        {"timestamp": ["2022-04-28 12:33:30.111", "2022-04-28 12:33:29.120"], "TP2": [1.0, 2.0],
         "COMP": [0.0, 1.0], "gpsLat": [41.1, 41.2], "gpsLong": [-8.6, -8.7], "gpsSpeed": [1.0, 2.0], "gpsQuality": [1.0, 1.0]}  # noqa: E501
    )  # fmt: skip
    out = ev.metropt_view(raw)
    assert list(out.columns) == ["timestamp", "TP2", "COMP"]
    assert out["TP2"].tolist() == [2.0, 1.0]  # time order
    assert out["timestamp"].iloc[0] == pd.Timestamp("2022-04-28 12:33:29.120")


def test_the_fugaku_and_metropt_builders_write_views_with_sampling_records(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "acquired"
    raw = root / "zen_fdata_fugaku" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(_fdata_frame(), preserve_index=False), raw / "21_04.parquet"
    )
    m = root / "zen_metropt2" / SNAP / "raw"
    m.mkdir(parents=True)
    (m / "MetroPT2_head.csv").write_bytes(
        b"timestamp,TP2,gpsLat\n2022-04-28 12:33:29.120,1.0,41.1\n2022-04-28 12:33:30.111,2.0,41.2\n2022-04-28 12:33:31.1"  # noqa: E501
    )
    manifest = {}
    ev._build_fugaku(root, tmp_path / "o" / "deep", manifest)
    ev._build_metropt(root, tmp_path / "o" / "deep", manifest)
    jobs = tmp_path / "o" / "deep" / "zen_fdata_fugaku" / "jobs.csv"
    assert len(pd.read_csv(jobs)) == 3
    f = manifest["zen_fdata_fugaku"]
    assert f["files"] == {"jobs.csv": {"sha256": _sha(jobs), "rows": 3}}
    assert f["sampling"] == {
        "method": "all rows of one monthly Parquet file (2021-04); the other months were not fetched",  # noqa: E501
        "rows_read": 3,
        "source_rows": 3,
        "truncated": False,
    }
    series = tmp_path / "o" / "deep" / "zen_metropt2" / "series.csv"
    assert (
        series.read_text().splitlines()[0] == "timestamp,TP2"
        and len(series.read_text().splitlines()) == 3
    )
    g = manifest["zen_metropt2"]
    assert g["sampling"] == {
        "method": "time-ordered prefix of the CSV (HTTP range from byte 0), not random",
        "bytes_cut_partial_line": 21,
        "rows_dropped": 0,
    }
    assert g["dropped"] == ["GPS position, speed and quality columns"]


# --- Open Library editions (complete nested catalogue records from a dump prefix) -----------------


def _ol_line(number, **extra):
    record = {"key": f"/books/OL{number}M", "type": {"key": "/type/edition"}, "title": f"t{number}",
              "authors": [{"key": "/authors/OL1A"}], "notes": {"type": "/type/text", "value": "free text"}, **extra}  # fmt: skip  # noqa: E501
    return f"/type/edition\t/books/OL{number}M\t3\t2020-01-01T00:00:00.1\t{json.dumps(record)}"


def test_open_library_view_keeps_a_deterministic_hash_subset_drops_free_text_and_sorts_by_key():
    lines = [_ol_line(n, description="d", publishers=["P"]) for n in (5, 3, 9, 1, 7, 2)]
    bad = ["", "only\ttwo", "/type/edition\tk\t1\t2020\tnot json"]
    kept, skipped = ev.open_library_view(lines + bad, modulo=1)
    assert [r["key"] for r in kept] == [f"/books/OL{n}M" for n in (1, 2, 3, 5, 7, 9)]
    assert (
        "notes" not in kept[0] and "description" not in kept[0] and kept[0]["publishers"] == ["P"]
    )
    assert (
        kept[0]["authors"] == [{"key": "/authors/OL1A"}] and skipped == 2
    )  # blank lines are not counted
    some, _ = ev.open_library_view(lines, modulo=2)
    import hashlib as _h

    expected = sorted(
        r
        for r in (f"/books/OL{n}M" for n in (5, 3, 9, 1, 7, 2))
        if int(_h.sha256(r.encode()).hexdigest(), 16) % 2 == 0
    )
    assert [r["key"] for r in some] == expected and 0 < len(some) < 6
    assert ev.open_library_view(lines, modulo=2)[0] == some  # same subset every time


def test_the_open_library_builder_reads_the_gzip_prefix_and_records_the_cut(tmp_path, monkeypatch):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "openlibrary_dump" / SNAP / "raw"
    raw.mkdir(parents=True)
    blob = gzip.compress(("\n".join(_ol_line(n) for n in range(1, 30)) + "\n").encode())
    (raw / "editions_head.txt.gz").write_bytes(blob[: len(blob) * 4 // 5])
    monkeypatch.setattr(ev, "OPENLIBRARY_MODULO", 1)
    manifest = {}
    ev._build_openlibrary(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "openlibrary_dump" / "editions.jsonl"
    rows = [json.loads(x) for x in target.read_text().splitlines()]
    view = manifest["openlibrary_dump"]
    assert len(rows) == view["files"]["editions.jsonl"]["rows"] > 0 and "notes" not in rows[0]
    assert view["sampling"]["stream_complete"] is False and view["sampling"]["modulo"] == 1
    assert view["sampling"]["lines_read"] >= len(rows) and view["sampling"]["lines_skipped"] == 0
    assert view["sampling"]["method"].startswith(
        "gzip prefix of the editions dump in key-text order"
    )
    assert view["dropped"] == ["notes", "description", "first_sentence", "table_of_contents"]


def test_blank_keys_are_missing_not_orphans_in_relation_checks():
    tables = {
        "a": pd.DataFrame({"k": ["1", "", "9", None]}),
        "b": pd.DataFrame({"k": ["1", ""]}),
    }
    spec = {
        "tables": {"a": {"keep": ["k"]}, "b": {"keep": ["k"]}},
        "relations": [["a", "k", "b", "k"]],
    }
    _, relations = ev.tables_view(tables, spec)
    assert relations == [
        {"child": "a.k", "parent": "b.k", "checked": 2, "orphans": 1, "share": 0.5}
    ]


# --- AEGIS OBD signals: one value per pid and second, relative time, no dates or positions -------


def test_the_aegis_view_pivots_pids_to_seconds_since_trip_start_and_drops_absolute_time():
    raw = pd.DataFrame(
        {
            "obdData_id": range(1, 8),
            "trip_id": [2, 2, 2, 2, 1, 1, 1],
            "obdPid": ["0C", "0D", "0C", "0D", "0C", "0C", "0D"],
            "data": ["10", "20", "30", "40", "5", "7", "x"],
            "timestamp": ["2017-01-19 10:00:00.1", "2017-01-19 10:00:00.5", "2017-01-19 10:00:01.2",
                          "2017-01-19 10:00:01.6", "2017-02-01 08:00:00.0", "2017-02-01 08:00:00.9", "2017-02-01 08:00:02.0"],  # noqa: E501
        }
    )  # fmt: skip
    out = ev.aegis_obd_view(raw)
    assert list(out.columns) == ["trip_id", "t_s", "pid_0C", "pid_0D"]
    assert out[["trip_id", "t_s"]].values.tolist() == [[1, 0], [1, 2], [2, 0], [2, 1]]
    first = out.iloc[0]
    assert first["pid_0C"] == 6.0 and pd.isna(first["pid_0D"])  # mean of 5 and 7 inside second 0
    assert pd.isna(out.iloc[1]["pid_0D"])  # an unreadable value stays missing
    assert out.iloc[2]["pid_0C"] == 10.0 and out.iloc[3]["pid_0D"] == 40.0
    assert "timestamp" not in out
    with pytest.raises(ev.ViewError, match="column"):
        ev.aegis_obd_view(raw.drop(columns=["data"]))


def test_the_aegis_builder_reads_only_the_obd_member_and_records_what_was_dropped(tmp_path):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "zen_aegis_vehicle" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "Automotive-ResearchDataSet-VIF-AEGIS.zip", "w") as z:
        z.writestr(
            "obdData.csv",
            '"obdData_id","trip_id","obdPid","data","timestamp"\n"1","3","0C","9","2017-01-19 16:19:03.045593"\n',  # noqa: E501
        )
        z.writestr("positions.csv", '"lat","lon"\n"47.0","15.4"\n')
    manifest = {}
    ev._build_aegis(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_aegis_vehicle" / "obd.csv"
    assert target.read_text() == "trip_id,t_s,pid_0C\n3,0,9.0\n"
    view = manifest["zen_aegis_vehicle"]
    assert view["files"] == {"obd.csv": {"sha256": _sha(target), "rows": 1}}
    assert view["dropped"] == [
        "positions",
        "gyroscopes",
        "accelerations",
        "absolute dates and times",
        "trip dates",
        "vehicle names",
    ]
    assert (
        view["notes"]
        == "one driver and one vehicle (35 trips); relative time inside each trip only"
    )


# --- CLUE-LDS user events from a zip prefix ------------------------------------------------------


def _clue(n, uid="u-a", kind="file_accessed", **over):
    record = {"params": {"path": "/secret/file"}, "type": kind, "time": f"2017-07-07T08:57:{n:02d}Z", "uid": uid, "id": n, "uidType": "name",  # noqa: E501
              "location": {"city": "Graz", "latitude": 47.0}, **over}  # fmt: skip
    return json.dumps(record)


def test_clue_view_keeps_type_time_role_and_pseudonymous_user_and_drops_params_and_location():
    lines = [
        _clue(2, uid="u-b", role="sales", isLocalIP=True),
        _clue(1),
        "",
        _clue(3, uid="1.2.3.4", uidType="ip"),
    ]
    out = ev.clue_events_view(lines)
    assert list(out.columns) == list(ev.CLUE_COLUMNS)
    assert ev.CLUE_COLUMNS == ("event_id", "time", "user", "type", "role", "is_local_ip")
    assert out["event_id"].tolist() == [1, 2, 3] and out["type"].tolist() == ["file_accessed"] * 3
    assert out["time"].iloc[0] == pd.Timestamp("2017-07-07 08:57:01", tz="UTC")
    assert out["user"].tolist() == [
        ev.pseudonym("u-a"),
        ev.pseudonym("u-b"),
        ev.pseudonym("1.2.3.4"),
    ]
    assert out["role"].tolist()[1] == "sales" and pd.isna(out["role"].iloc[0])
    assert out["is_local_ip"].tolist()[1] is True or out["is_local_ip"].iloc[1] == True  # noqa: E712
    assert "params" not in out and "location" not in out and "uid" not in out
    assert len(ev.clue_events_view([])) == 0


def test_the_clue_builder_reads_the_zip_prefix_caps_the_events_and_records_the_cut(
    tmp_path, monkeypatch
):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "zen_clue_lds" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "clue_head.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "clue.json", "\n".join(_clue(n % 50, uid=f"u{n % 4}") for n in range(400)) + "\n"
        )
    blob = (raw / "clue_head.zip").read_bytes()
    (raw / "clue_head.zip").write_bytes(blob[: len(blob) * 3 // 4])
    monkeypatch.setattr(ev, "CLUE_MAX_EVENTS", 100)
    manifest = {}
    ev._build_clue(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_clue_lds" / "events.csv"
    assert len(pd.read_csv(target)) == 100
    view = manifest["zen_clue_lds"]
    assert view["files"] == {"events.csv": {"sha256": _sha(target), "rows": 100}}
    assert view["sampling"]["stream_complete"] is False and view["sampling"]["events_kept"] == 100
    assert view["sampling"]["events_read"] >= 100 and view["sampling"]["method"].startswith(
        "zip prefix of clue.json"
    )
    assert view["dropped"] == ["params (paths, groups)", "location", "uidType"]
    assert view["pseudonymised"] == ["user"]


# --- XES event logs (process-mining logs of real organisations) -----------------------------------

XES = """<?xml version="1.0" encoding="UTF-8"?>
<log xes.version="1.0">
 <trace><string key="concept:name" value="c1"/>
  <event><string key="concept:name" value="A"/>
   <date key="time:timestamp" value="2012-01-01T10:00:00.000+01:00"/>
   <string key="lifecycle:transition" value="START"/><string key="org:resource" value="r1"/>
   <float key="amount" value="5.5"/></event>
  <event><string key="concept:name" value="B"/>
   <date key="time:timestamp" value="2012-01-01T11:00:00.000+01:00"/></event>
 </trace>
 <trace><string key="concept:name" value="c2"/>
  <event><string key="concept:name" value="A"/>
   <date key="time:timestamp" value="2012-01-02T10:00:00.000+01:00"/>
   <int key="amount" value="7"/></event>
 </trace>
 <trace><string key="concept:name" value="c3"/>
  <event><string key="concept:name" value="C"/>
   <date key="time:timestamp" value="2012-01-03T10:00:00.000+01:00"/></event>
</log>
"""


def test_the_xes_view_flattens_events_orders_cases_by_hash_pseudonymises_resources_and_keeps_listed_numbers():  # noqa: E501
    import io

    import xes_stream

    fixed = XES.replace("</event>\n</log>", "</event></trace></log>")
    traces = xes_stream.read_traces(io.BytesIO(fixed.encode())).traces
    out = ev.xes_view(traces, modulo=1, numeric=["amount"])
    assert list(out.columns) == [
        "case_id",
        "position",
        "time",
        "activity",
        "transition",
        "resource",
        "amount",
    ]
    assert out["case_id"].tolist() == ["c1", "c1", "c2", "c3"] and out["position"].tolist() == [
        0,
        1,
        0,
        0,
    ]
    assert out["activity"].tolist() == ["A", "B", "A", "C"]
    assert out["time"].iloc[0] == pd.Timestamp("2012-01-01 09:00:00", tz="UTC")  # normalised to UTC
    assert out["resource"].iloc[0] == ev.pseudonym("r1") and pd.isna(out["resource"].iloc[1])
    assert out["transition"].iloc[0] == "START" and pd.isna(out["transition"].iloc[2])
    assert (
        out["amount"].tolist()[0] == 5.5
        and pd.isna(out["amount"].iloc[1])
        and out["amount"].iloc[2] == 7.0
    )
    import hashlib as _h

    some = ev.xes_view(traces, modulo=2, numeric=[])
    want = [c for c in ("c1", "c2", "c3") if int(_h.sha256(c.encode()).hexdigest(), 16) % 2 == 0]
    assert sorted(some["case_id"].unique().tolist()) == want and "amount" not in some


def test_the_xes_builder_reads_gz_and_plain_files_and_records_cut_and_sampling(
    tmp_path, monkeypatch
):
    import gzip

    root = tmp_path / "acquired"
    for name, raw_name, data in (
        (
            "4tu_a",
            "log.xes.gz",
            gzip.compress(XES.replace("</event>\n</log>", "</event></trace></log>").encode()),
        ),
        ("4tu_b", "head.xes", XES[: XES.index('value="c3"')].encode()),
    ):
        folder = root / name / SNAP / "raw"
        folder.mkdir(parents=True)
        (folder / raw_name).write_bytes(data)
    monkeypatch.setattr(ev, "XES_SPECS", {
        "4tu_a": {"file": "log.xes.gz", "modulo": 1, "numeric": ["amount"], "partial": False},
        "4tu_b": {"file": "head.xes", "modulo": 1, "numeric": [], "partial": True}})  # fmt: skip
    manifest = {}
    ev._build_xes(root, tmp_path / "o" / "deep", manifest)
    a, b = manifest["4tu_a"], manifest["4tu_b"]
    assert a["files"]["events.csv"]["rows"] == 4 and a["sampling"] == {"cases_read": 3, "cases_kept": 3, "modulo": 1, "stream_complete": True, "stop": "log_closed", "source_fragment": False, "selection": "complete traces in log order, then one case in 1 by case-name hash; a prefix of the log is not a random sample"}  # fmt: skip  # noqa: E501
    assert b["files"]["events.csv"]["rows"] == 3 and b["sampling"]["cases_read"] == 2
    assert b["sampling"]["stream_complete"] is False and b["sampling"]["source_fragment"] is True
    assert b["sampling"]["stop"] == "input_ended_before_log_closed"
    assert a["pseudonymised"] == ["resource"] and a["dropped"] == ["all trace and event attributes except activity, time, transition, resource and listed numbers"]  # fmt: skip  # noqa: E501


# --- CSV event logs with an explicit schema mapping (one row is one event) ------------------------

CSV_SPEC = {
    "case": "Incident ID", "activity": "Type", "time": "Stamp", "format": "%d-%m-%Y %H:%M:%S",
    "order": "Num", "resource": "Group", "modulo": 1, "sep": ";",
}  # fmt: skip


def _csv_events():
    return pd.DataFrame(
        {
            "Incident ID": ["I2", "I1", "I1", "I1", "I3"],
            "Type": ["Open", "Closed", "Open", "Assign", None],
            "Stamp": ["02-01-2013 10:00:00", "05-01-2013 09:00:00", "01-01-2013 08:00:00",
                      "01-01-2013 08:00:00", "03-01-2013 10:00:00"],
            "Num": ["002", "003", "001", "00A", "004"],
            "Group": ["T1", "T2", "T1", "T1", "T3"],
        }
    )  # fmt: skip


def test_csv_event_view_orders_each_case_by_time_then_the_source_sequence_and_drops_unusable_rows():
    out, info = ev.csv_event_view(_csv_events(), CSV_SPEC)
    assert list(out.columns) == [
        "case_id",
        "position",
        "time",
        "activity",
        "transition",
        "resource",
    ]
    assert out["case_id"].tolist() == ["I1", "I1", "I1", "I2"]
    assert out["activity"].tolist() == ["Open", "Assign", "Closed", "Open"]  # tie broken by Num
    assert out["position"].tolist() == [0, 1, 2, 0]
    assert out["time"].iloc[0] == pd.Timestamp("2013-01-01 08:00:00", tz="UTC")
    assert out["resource"].iloc[0] == ev.pseudonym("T1") and out["transition"].isna().all()
    assert info == {
        "rows": 5,
        "rows_without_activity": 1,
        "rows_without_time": 0,
        "cases": 3,
        "cases_kept": 2,
    }


def test_csv_event_view_counts_unreadable_times_and_selects_cases_by_hash():
    frame = _csv_events()
    frame.loc[0, "Stamp"] = "not a date"
    out, info = ev.csv_event_view(frame, {**CSV_SPEC, "modulo": 1})
    assert info["rows_without_time"] == 1 and "I2" not in out["case_id"].tolist()
    import hashlib as _h

    some, rep = ev.csv_event_view(_csv_events(), {**CSV_SPEC, "modulo": 2})
    want = {c for c in ("I1", "I2") if int(_h.sha256(c.encode()).hexdigest(), 16) % 2 == 0}
    assert set(some["case_id"]) == want and rep["cases_kept"] == len(want)
    with pytest.raises(ev.ViewError, match="column 'Stamp'"):
        ev.csv_event_view(frame.drop(columns=["Stamp"]), CSV_SPEC)


def test_the_csv_event_builder_reads_the_declared_file_and_records_the_mapping(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "4tu_csv" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "log.csv").write_text(
        "Incident ID;Type;Stamp;Num;Group\nI1;Open;01-01-2013 08:00:00;001;T1\nI1;Closed;02-01-2013 08:00:00;002;T1\n"  # noqa: E501
    )
    monkeypatch.setattr(ev, "CSV_EVENT_SPECS", {"4tu_csv": {**CSV_SPEC, "file": "log.csv"}})
    manifest = {}
    ev._build_csv_events(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "4tu_csv" / "events.csv"
    assert len(pd.read_csv(target)) == 2
    view = manifest["4tu_csv"]
    assert view["files"] == {"events.csv": {"sha256": _sha(target), "rows": 2}}
    assert view["sampling"]["cases_kept"] == 1 and view["sampling"]["rows_without_time"] == 0
    assert view["sampling"]["mapping"] == {"case": "Incident ID", "activity": "Type", "time": "Stamp", "order": "Num", "resource": "Group"}  # fmt: skip  # noqa: E501
    assert view["pseudonymised"] == ["resource"]


def test_table_sets_support_other_member_extensions_and_skip_missing_optional_tables(
    tmp_path, monkeypatch
):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "feed_a" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "gtfs.zip", "w") as z:
        z.writestr("routes.txt", "route_id,route_name\nR1,x\n")
        z.writestr("trips.txt", "trip_id,route_id\nT1,R1\nT2,R9\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"feed_a": {
        "archive": {"file": "gtfs.zip", "prefix": "", "ext": ".txt"}, "sep": ",", "quote_none": False,  # noqa: E501
        "dropped": ["names"],
        "tables": {"routes": {"keep": ["route_id"]}, "trips": {"keep": ["trip_id", "route_id"]},
                   "calendar": {"keep": ["service_id"], "optional": True}},
        "relations": [["trips", "route_id", "routes", "route_id"], ["trips", "service_id", "calendar", "service_id"]]}})  # fmt: skip  # noqa: E501
    manifest = {}
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "feed_a"
    assert sorted(p.name for p in folder.iterdir()) == [
        "routes.csv",
        "trips.csv",
    ]  # no calendar table
    view = manifest["feed_a"]
    assert sorted(view["files"]) == ["routes.csv", "trips.csv"]
    assert view["relations"] == [{"child": "trips.route_id", "parent": "routes.route_id", "checked": 2, "orphans": 1, "share": 0.5}]  # fmt: skip  # noqa: E501
    assert view["notes"].endswith("; optional tables absent from the archive: calendar")


# --- Met Museum catalogue records (nested JSON, one request per object) ----------------------------  # noqa: E501


def test_met_view_drops_biographies_and_images_deduplicates_and_sorts_by_object_id():
    records = [
        {"objectID": 9, "title": "b", "artistDisplayBio": "bio text", "primaryImage": "u", "additionalImages": ["x"],  # noqa: E501
         "constituents": [{"name": "n", "role": "Artist"}], "measurements": [{"elementName": "Overall", "elementMeasurements": {"Height": 1.5}}]},  # noqa: E501
        {"objectID": 3, "title": "a", "artistDisplayBio": "other", "tags": None},
        {"objectID": 9, "title": "b again"},
    ]  # fmt: skip
    out = ev.met_objects_view(records)
    assert [r["objectID"] for r in out] == [3, 9] and out[1][
        "title"
    ] == "b"  # first record per id wins
    assert (
        "artistDisplayBio" not in out[0]
        and "primaryImage" not in out[1]
        and "additionalImages" not in out[1]
    )
    assert out[1]["constituents"] == [{"name": "n", "role": "Artist"}]
    assert out[1]["measurements"][0]["elementMeasurements"] == {
        "Height": 1.5
    }  # nested values are kept
    assert records[0]["artistDisplayBio"] == "bio text"  # the input is untouched


def test_the_met_builder_reads_the_object_files_in_id_order_and_counts_unreadable_ones(tmp_path):
    root = tmp_path / "acquired"
    raw = root / "met_museum_objects" / SNAP / "raw"
    raw.mkdir(parents=True)
    for i in (20, 5, 11):
        (raw / f"obj_{i}.json").write_text(
            json.dumps({"objectID": i, "title": f"t{i}", "artistDisplayBio": "x"})
        )
    (raw / "obj_99.json").write_text("not json")
    (raw / "manifest.json").write_text("{}")  # not an object file
    manifest = {}
    ev._build_met(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "met_museum_objects" / "objects.jsonl"
    rows = [json.loads(x) for x in target.read_text().splitlines()]
    assert [r["objectID"] for r in rows] == [5, 11, 20] and "artistDisplayBio" not in rows[0]
    view = manifest["met_museum_objects"]
    assert view["files"] == {"objects.jsonl": {"sha256": _sha(target), "rows": 3}}
    assert view["sampling"] == {"object_files": 4, "unreadable": 1, "method": "object ids chosen as an even stride over the sorted listing, not random"}  # fmt: skip  # noqa: E501
    assert view["dropped"] == [
        "artistDisplayBio",
        "primaryImage",
        "primaryImageSmall",
        "additionalImages",
    ]


# --- Environment Agency daily river flow: one csv per station, one network -----------------------


def test_the_flow_builder_stacks_stations_into_a_panel_and_records_quality_shares(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
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
    monkeypatch.setattr(ev, "EA_STATIONS", ["s1", "s2"])
    manifest = {}
    ev._build_ea(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "ea_hydrology_flow" / "flow.csv"
    assert (
        target.read_text()
        == "timestamp,station,value\n2020-01-01,s1,1.5\n2020-01-02,s1,2.5\n2020-01-01,s2,\n"
    )
    view = manifest["ea_hydrology_flow"]
    assert view["files"] == {"flow.csv": {"sha256": _sha(target), "rows": 3}}
    assert view["sampling"] == {"stations": 2, "rows_dropped": 0, "complete_share": 0.6667, "missing_value_share": 0.3333,  # noqa: E501
                                "method": "daily mean flow of stations chosen as an even stride over the sorted measure list"}  # fmt: skip  # noqa: E501


# --- French property transactions (DVF): privacy-reduced sales rows --------------------------------  # noqa: E501


def _dvf_frame():
    return pd.DataFrame(
        {
            "id_mutation": ["2024-2", "2024-1", "2024-1", "2024-3"],
            "date_mutation": ["2024-01-03", "2024-01-02", "2024-01-02", "2024-02-01"],
            "nature_mutation": ["Vente", "Vente", "Vente", "Echange"],
            "valeur_fonciere": ["10000", "346.5", "346.5", ""],
            "adresse_nom_voie": ["RUE A", "RUE B", "RUE B", "RUE C"],
            "id_parcelle": ["p1", "p2", "p2", "p3"],
            "code_commune": ["69123", "69123", "69123", "69381"],
            "type_local": ["Maison", "Appartement", None, "Maison"],
            "surface_reelle_bati": ["100", "50", "", "80"],
            "nombre_pieces_principales": ["4", "2", "", "3"],
            "surface_terrain": ["500", "", "20", "300"],
            "longitude": ["4.8", "4.9", "4.9", "4.7"],
            "latitude": ["45.7", "45.8", "45.8", "45.6"],
        }
    )  # fmt: skip


def test_dvf_view_keeps_commercial_fields_pseudonymises_the_mutation_and_drops_addresses_and_positions():  # noqa: E501
    out = ev.dvf_view(_dvf_frame())
    assert list(out.columns) == list(ev.DVF_COLUMNS)
    assert ev.DVF_COLUMNS == (
        "mutation", "date", "nature", "value_eur", "commune", "local_type", "built_area_m2", "rooms", "land_area_m2",  # noqa: E501
    )  # fmt: skip
    assert out["date"].tolist() == sorted(out["date"].tolist())  # date order
    assert out["mutation"].iloc[0] == ev.pseudonym("2024-1") and out["mutation"].iloc[
        2
    ] == ev.pseudonym("2024-2")
    assert out["value_eur"].tolist()[:2] == [346.5, 346.5] and pd.isna(out["value_eur"].iloc[3])
    assert out["commune"].tolist()[0] == "69123" and out["local_type"].iloc[0] == "Appartement"
    assert pd.isna(out["rooms"].iloc[1]) and out["land_area_m2"].iloc[1] == 20.0
    for gone in ("adresse_nom_voie", "id_parcelle", "longitude", "latitude", "id_mutation"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column 'valeur_fonciere'"):
        ev.dvf_view(_dvf_frame().drop(columns=["valeur_fonciere"]))


def test_the_dvf_builder_reads_the_gzip_csv_and_records_the_department_scope(tmp_path):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "dgfip_dvf" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "dvf_69_2024.csv.gz").write_bytes(
        gzip.compress(_dvf_frame().to_csv(index=False).encode())
    )
    manifest = {}
    ev._build_dvf(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "dgfip_dvf" / "sales.csv"
    assert len(pd.read_csv(target)) == 4
    view = manifest["dgfip_dvf"]
    assert view["files"] == {"sales.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["pseudonymised"] == ["mutation"] and "address" in view["dropped"][0]
    assert view["sampling"] == {"scope": "department 69 (Rhone), transactions of 2024 only", "rows": 4, "rows_without_value": 1}  # fmt: skip  # noqa: E501


def test_the_gtfs_template_keeps_only_keys_and_the_three_relations_and_registers_every_feed():
    spec = ev._gtfs_spec("feed.zip")
    assert spec == {
        "archive": {"file": "feed.zip", "prefix": "", "ext": ".txt"},
        "sep": ",",
        "quote_none": False,
        "dropped": ["stop and route names", "coordinates", "shapes", "fares", "free text"],
        "tables": {
            "routes": {"keep": ["route_id", "route_type"]},
            "trips": {"keep": ["trip_id", "route_id", "service_id"]},
            "stop_times": {"keep": ["trip_id", "stop_id", "stop_sequence"]},
            "stops": {"keep": ["stop_id"]},
            "calendar_dates": {"keep": ["service_id", "date", "exception_type"], "optional": True},
        },
        "relations": [
            ["trips", "route_id", "routes", "route_id"],
            ["stop_times", "trip_id", "trips", "trip_id"],
            ["stop_times", "stop_id", "stops", "stop_id"],
        ],
    }
    assert len(ev.GTFS_FEEDS) == 12 and all(
        name.endswith(".zip") for name in ev.GTFS_FEEDS.values()
    )
    assert all(
        source in ev.TABLE_SETS for source in ev.GTFS_FEEDS
    )  # the real registry holds every feed


# --- UK Price Paid Data (property sales of England and Wales) --------------------------------------  # noqa: E501

PPD_HEAD = (
    '"{A}","320000","2024-03-20 00:00","NR9 5FP","D","Y","F","24","","DUSTY MILLER DRIVE","EASTON",'
    '"NORWICH","SOUTH NORFOLK","NORFOLK","A","A"\n'
    '"{B}","291000","2024-01-26 00:00","NR20 3UF","S","N","L","8","FLAT 2","CLIFTONVILLE DRIVE","",'
    '"DEREHAM","BRECKLAND","NORFOLK","B","A"\n'
)


def test_price_paid_view_keeps_the_commercial_fields_a_postcode_district_and_a_salted_transaction_id():  # noqa: E501
    frame, cut = ev.csv_prefix_no_header(PPD_HEAD.encode() + b'"{C}","1","2024')
    assert cut == len(b'"{C}","1","2024') and len(frame) == 2
    out = ev.price_paid_view(frame)
    assert list(out.columns) == list(ev.PPD_COLUMNS)
    assert ev.PPD_COLUMNS == (
        "transaction", "price_gbp", "date", "postcode_district", "property_type", "new_build",
        "tenure", "county", "ppd_category", "status",
    )  # fmt: skip
    assert out["date"].tolist() == ["2024-01-26", "2024-03-20"]  # date order, time of day dropped
    assert out["price_gbp"].tolist() == [291000, 320000] and str(out["price_gbp"].dtype) == "int64"
    assert out["postcode_district"].tolist() == ["NR20", "NR9"]
    assert out["transaction"].tolist() == [ev.pseudonym("{B}"), ev.pseudonym("{A}")]
    assert out["property_type"].tolist() == ["S", "D"] and out["new_build"].tolist() == ["N", "Y"]
    assert out["tenure"].tolist() == ["L", "F"] and out["county"].tolist() == ["NORFOLK", "NORFOLK"]
    assert out["ppd_category"].tolist() == ["B", "A"] and out["status"].tolist() == ["A", "A"]
    for gone in ("street", "paon", "saon", "locality", "town", "district"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="16 columns"):
        ev.price_paid_view(frame.iloc[:, :10])


def test_the_price_paid_builder_reads_the_fragment_and_records_the_cut_and_the_scope(tmp_path):
    root = tmp_path / "acquired"
    raw = root / "hmlr_price_paid" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "pp-2024_head.csv").write_bytes(PPD_HEAD.encode() + b'"{C}","5000')
    manifest = {}
    ev._build_ppd(root, tmp_path / "o" / "deep", manifest)
    ev._build_ppd(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "hmlr_price_paid" / "sales.csv"
    assert len(pd.read_csv(target)) == 2
    view = manifest["hmlr_price_paid"]
    assert view["files"] == {"sales.csv": {"sha256": _sha(target), "rows": 2}}
    assert view["pseudonymised"] == ["transaction"] and view["salt_label"] == ev.SALT
    assert view["dropped"] == [
        "street, house number, flat, locality, town and district",
        "postcode unit",
    ]
    assert view["sampling"] == {"method": "first bytes of the 2024 file (HTTP range from byte 0), file order, not random", "rows": 2, "bytes_cut_partial_line": 11}  # fmt: skip  # noqa: E501


# --- Online Retail invoice lines (UK e-commerce) ----------------------------------------------------  # noqa: E501


def _retail_frame():
    return pd.DataFrame(
        {
            "InvoiceNo": ["536366", "C536379", "536365", "536365"],
            "StockCode": ["22633", "D", "85123A", "71053"],
            "Description": ["HAND WARMER", "Discount", "WHITE HANGING HEART", "WHITE METAL LANTERN"],  # noqa: E501
            "Quantity": ["6", "-1", "6", "x"],
            "InvoiceDate": ["12/1/2010 8:28", "12/1/2010 9:41", "12/1/2010 8:26", "12/1/2010 8:26"],
            "UnitPrice": ["1.85", "27.50", "2.55", "3.39"],
            "CustomerID": ["17850", None, "17850", "13047.0"],
            "Country": ["United Kingdom", "United Kingdom", "United Kingdom", "France"],
        }
    )  # fmt: skip


def test_retail_view_pseudonymises_invoices_and_customers_flags_cancellations_and_computes_line_values():  # noqa: E501
    out = ev.retail_view(_retail_frame())
    assert list(out.columns) == list(ev.RETAIL_COLUMNS)
    assert ev.RETAIL_COLUMNS == (
        "timestamp", "invoice", "stock_code", "quantity", "unit_price", "line_value", "customer", "country", "cancellation",  # noqa: E501
    )  # fmt: skip
    assert out["timestamp"].tolist() == sorted(out["timestamp"].tolist())
    assert out["invoice"].tolist()[:2] == [ev.pseudonym("536365")] * 2
    assert out["cancellation"].tolist() == [
        False,
        False,
        False,
        True,
    ]  # the invoice number starts with C
    assert out["customer"].iloc[0] == ev.pseudonym("17850") and pd.isna(out["customer"].iloc[3])
    assert out["customer"].iloc[1] == ev.pseudonym(
        "13047"
    )  # a float-formatted id is the same customer
    assert (
        out["line_value"].iloc[0] == pytest.approx(15.3)
        and out["quantity"].iloc[1] != out["quantity"].iloc[1]
    )  # x is missing
    assert pd.isna(out["line_value"].iloc[1])
    assert out["cancellation"].dtype == bool and out["stock_code"].tolist()[0] == "85123A"
    for gone in ("Description", "InvoiceNo", "CustomerID"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column 'UnitPrice'"):
        ev.retail_view(_retail_frame().drop(columns=["UnitPrice"]))


def test_the_retail_builder_reads_the_pinned_table_and_records_what_it_dropped(tmp_path):
    root = tmp_path / "acquired"
    (tmp_path / "uci_wave2").mkdir()
    _retail_frame().to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    manifest: dict = {}
    ev._build_retail(root, tmp_path / "o", manifest)
    ev._build_retail(root, tmp_path / "o", manifest)
    target = tmp_path / "o" / "uci_online_retail" / "lines.csv"
    assert len(pd.read_csv(target)) == 4 and target.read_text().splitlines()[0] == ",".join(
        ev.RETAIL_COLUMNS
    )
    view = manifest["uci_online_retail"]
    assert view["files"] == {"lines.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["dropped"] == ["product description (free text)"] and view["pseudonymised"] == [
        "invoice",
        "customer",
    ]
    assert view["salt_label"] == ev.SALT and view["sampling"] == {
        "rows_in": 4,
        "cancellations": 1,
        "rows_without_customer": 1,
    }
    assert view["source_snapshot"] == "uci:352 (repository file pinned by checksum)"


def test_retail_view_turns_unreadable_prices_customers_and_dates_into_missing_values():
    raw = _retail_frame()
    raw.loc[0, "UnitPrice"] = "n/a"
    raw.loc[2, "CustomerID"] = "unknown"
    raw.loc[3, "InvoiceDate"] = "not a date"
    out = ev.retail_view(raw)
    assert out["timestamp"].isna().sum() == 1 and out["timestamp"].iloc[-1] is pd.NaT
    assert out["unit_price"].isna().sum() == 1 and out["line_value"].isna().sum() >= 1
    assert out["customer"].isna().sum() == 2  # the missing id and the unreadable one
    ok = ev.retail_view(
        pd.DataFrame({**_retail_frame().to_dict("list"), "InvoiceDate": ["13/01/2010 9:00"] * 4})
    )
    assert ok["timestamp"].isna().all()  # the declared month-first layout rejects a day-first date


def test_retail_view_reads_dates_in_the_declared_month_first_layout():
    raw = _retail_frame()
    raw["InvoiceDate"] = ["12/1/2010 8:28", "1/12/2011 9:41", "12/13/2010 8:26", "2/3/2011 8:26"]
    out = ev.retail_view(raw)
    assert sorted(out["timestamp"].dt.month) == [1, 2, 12, 12]
    assert out["timestamp"].min() == pd.Timestamp("2010-12-01 08:28")


def test_the_retail_builder_keeps_codes_with_leading_zeros_as_text(tmp_path):
    root = tmp_path / "acquired"
    (tmp_path / "uci_wave2").mkdir()
    frame = _retail_frame()
    frame["StockCode"] = ["00123", "0042", "85123", "0007"]
    frame.to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    ev._build_retail(root, tmp_path / "o", {})
    out = pd.read_csv(tmp_path / "o" / "uci_online_retail" / "lines.csv", dtype=str)
    assert sorted(out["stock_code"]) == ["0007", "00123", "0042", "85123"]
    assert (
        out["quantity"].tolist().count("6.0") == 2
    )  # numbers were parsed by the view, not the reader


# --- Paleobiology Database occurrences ---------------------------------------------------------------  # noqa: E501


def _pbdb_frame():
    base = {c: ["x", " Mammalia ", "", None] for c in ev.PBDB_TEXT}
    base.update({c: ["1.5", "bad", "3", None] for c in ev.PBDB_NUMBER})
    base["occurrence_no"] = ["30", "10", "20", "x"]
    base["collection_no"] = ["1", "1", "2", "3"]
    base["accepted_no"] = ["30", "30", "50", None]
    base["reference_no"] = ["9", "9", "8", "7"]
    base["enterer"] = ["a person", "b", "c", "d"]  # contributor names must not reach the view
    base["collection_aka"] = ["free text"] * 4
    return pd.DataFrame(base)


def test_pbdb_view_keeps_the_named_columns_trims_text_and_turns_unreadable_numbers_into_missing():
    out = ev.pbdb_occurrence_view(_pbdb_frame())
    assert list(out.columns) == list(ev.PBDB_COLUMNS) and ev.PBDB_COLUMNS[0] == "occurrence_no"
    assert out["occurrence_no"].iloc[:3].tolist() == [10, 20, 30] and pd.isna(
        out["occurrence_no"].iloc[3]
    )
    assert out["class"].tolist() == [
        "Mammalia",
        pd.NA,
        "x",
        pd.NA,
    ]  # trimmed; blank and missing both missing
    assert out.loc[out["occurrence_no"] == 10, "max_ma"].isna().all()
    assert out.loc[out["occurrence_no"] == 30, "max_ma"].iloc[0] == 1.5
    assert "enterer" not in out and "collection_aka" not in out
    with pytest.raises(ev.ViewError, match="columns not found: .*'lat'"):
        ev.pbdb_occurrence_view(_pbdb_frame().drop(columns=["lat"]))


# --- Kelmarsh wind farm SCADA ------------------------------------------------------------------------  # noqa: E501


def _kelmarsh_text(turbine=1, rows=None, extra="Lost Production (kWh)"):
    """A file in the exported layout: comment lines, a commented column header, then data lines."""
    names = ["Date and time", *ev.KELMARSH_SIGNALS, extra]
    rows = rows if rows is not None else [
        ["2016-01-03 00:10:00"] + ["2.5"] * len(ev.KELMARSH_SIGNALS) + ["9"],
        ["2016-01-03 00:00:00"] + ["NaN"] * len(ev.KELMARSH_SIGNALS) + ["9"],
    ]  # fmt: skip
    head = f"# This file was exported by a tool.\n#\n# Turbine: Kelmarsh {turbine}\n#\n"
    header = "# " + ",".join(f'"{n}"' if "," in n else n for n in names)
    return head + header + "\n" + "\n".join(",".join(r) for r in rows) + "\n"


def _kelmarsh_zip(path, turbines=(1, 2), text=None):
    import zipfile as _zk

    with _zk.ZipFile(path, "w") as z:
        for t in turbines:
            z.writestr(
                f"Turbine_Data_Kelmarsh_{t}_2016-01-03_-_2017-01-01_22{t}.csv",
                text or _kelmarsh_text(t),
            )
            z.writestr(f"Status_Kelmarsh_{t}_2016-01-03_-_2017-01-01_22{t}.csv", "# status\n")


def test_kelmarsh_view_renames_signals_keeps_missing_values_and_sorts_by_time():
    names = ["Date and time", *ev.KELMARSH_SIGNALS]
    raw = pd.DataFrame(
        [["2016-01-03 00:10:00"] + [2.5] * len(ev.KELMARSH_SIGNALS),
         ["2016-01-03 00:00:00"] + [None] * len(ev.KELMARSH_SIGNALS),
         ["bad"] + [1.0] * len(ev.KELMARSH_SIGNALS)],
        columns=names,
    )  # fmt: skip
    out = ev.kelmarsh_view(raw, "T3")
    assert list(out.columns) == list(ev.KELMARSH_COLUMNS) and ev.KELMARSH_COLUMNS[:2] == (
        "timestamp",
        "turbine",
    )
    assert len(out) == 2 and out["turbine"].tolist() == [
        "T3",
        "T3",
    ]  # the unreadable time is dropped
    assert out["timestamp"].is_monotonic_increasing and out["wind_speed"].isna().tolist() == [
        True,
        False,
    ]
    assert out["power_kw"].iloc[1] == 2.5 and out["generator_rpm"].dtype == "float64"
    with pytest.raises(ev.ViewError, match="columns not found: .*Power"):
        ev.kelmarsh_view(raw.drop(columns=["Power (kW)"]), "T3")


def test_kelmarsh_header_is_found_in_the_comment_block_and_a_missing_one_is_an_error():
    lines = _kelmarsh_text().split("\n")
    index, header = ev._kelmarsh_header(lines)
    assert index == 4 and header[0] == "Date and time" and header[-1] == "Lost Production (kWh)"
    assert "Wind speed, Standard deviation (m/s)" not in header
    with pytest.raises(ev.ViewError, match="column header line not found"):
        ev._kelmarsh_header(["# nothing", "1,2"])


def test_the_kelmarsh_builder_stacks_the_turbines_reads_nan_as_missing_and_records_sampling(
    tmp_path,
):
    raw = tmp_path / "acquired" / "zen_kelmarsh" / SNAP / "raw"
    raw.mkdir(parents=True)
    _kelmarsh_zip(raw / "Kelmarsh_SCADA_2016_3082.zip")
    manifest: dict = {}
    ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", manifest)
    out = pd.read_csv(tmp_path / "o" / "zen_kelmarsh" / "series.csv")
    assert out["turbine"].tolist() == ["T1", "T1", "T2", "T2"]
    assert out["timestamp"].iloc[:2].tolist() == ["2016-01-03 00:00:00", "2016-01-03 00:10:00"]
    assert (
        out["wind_speed"].isna().tolist() == [True, False, True, False]
        and out["power_kw"].iloc[1] == 2.5
    )
    view = manifest["zen_kelmarsh"]
    assert view["sampling"] == {"method": view["sampling"]["method"], "turbines": 2, "rows_in": 4}
    assert (
        "2016" in view["sampling"]["method"] and view["source_snapshot"] == f"zen_kelmarsh/{SNAP}"
    )
    assert view["files"]["series.csv"]["rows"] == 4 and view["pseudonymised"] == []


def test_the_kelmarsh_builder_refuses_an_archive_without_turbine_files_or_header(tmp_path):
    import zipfile as _zk

    raw = tmp_path / "acquired" / "zen_kelmarsh" / SNAP / "raw"
    raw.mkdir(parents=True)
    with _zk.ZipFile(raw / "Kelmarsh_SCADA_2016_3082.zip", "w") as z:
        z.writestr("Status_Kelmarsh_1_x.csv", "# status\n")
    with pytest.raises(ev.ViewError, match="no turbine data file in the archive"):
        ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", {})
    _kelmarsh_zip(raw / "Kelmarsh_SCADA_2016_3082.zip", text="no header here\n1,2\n")
    with pytest.raises(ev.ViewError, match="column header line not found"):
        ev._build_kelmarsh(tmp_path / "acquired", tmp_path / "o", {})


# --- Wikidata items ----------------------------------------------------------------------------------  # noqa: E501


def _wd_item(number, instance=None, extra=None):
    claims = {}
    if instance:
        claims["P31"] = [{"mainsnak": {"datavalue": {"value": {"id": instance}}}}]
    item = {
        "id": f"Q{number}",
        "type": "item",
        "labels": {"en": {"language": "en", "value": f"x{number}"}},
        "claims": claims,
    }
    item.update(extra or {})
    return item


def test_wikidata_view_drops_people_keeps_everything_else_and_orders_by_identifier():
    records = [_wd_item(30, "Q5"), _wd_item(100, "Q13442814"), _wd_item(9), _wd_item(100, "Q5"), _wd_item(7, "Q5"),  # noqa: E501
               _wd_item(20, "Q6256", {"sitelinks": {"enwiki": {"title": "T"}}})]  # fmt: skip
    view, people = ev.wikidata_view(records)
    assert [r["id"] for r in view] == [
        "Q9",
        "Q20",
        "Q100",
    ] and people == 2  # Q100 keeps its first record
    assert (
        view[1]["sitelinks"] == {"enwiki": {"title": "T"}}
        and view[2]["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] == "Q13442814"
    )
    assert (
        ev.wikidata_view([])[1] == 0
        and ev.wikidata_view([_wd_item(1)])[0][0]["labels"]["en"]["value"] == "x1"
    )


def test_a_human_is_recognised_only_by_an_instance_of_human_claim():
    assert (
        ev._is_human(_wd_item(1, "Q5"))
        and not ev._is_human(_wd_item(1, "Q6256"))
        and not ev._is_human(_wd_item(1))
    )
    odd = {
        "id": "Q1",
        "claims": {
            "P31": [
                {"mainsnak": {"snaktype": "novalue"}},
                {"mainsnak": {"datavalue": {"value": "Q5"}}},
            ]
        },
    }
    assert not ev._is_human(odd)
    assert not ev._is_human(
        {"id": "Q1", "claims": {"P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}}
    )


def test_the_wikidata_builder_skips_missing_items_counts_people_and_writes_sorted_json_lines(
    tmp_path,
):
    raw = tmp_path / "acquired" / "wikidata_entities" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "entities_01.json").write_text(
        json.dumps({"entities": {"Q50": _wd_item(50), "Q51": {"id": "Q51", "missing": ""}}})
    )
    (raw / "entities_00.json").write_text(
        json.dumps(
            {
                "entities": {
                    "Q5000": _wd_item(5000, "Q5"),
                    "Q40": _wd_item(40, "Q1", {"z": 1, "a": 2}),
                }
            }
        )
    )
    manifest: dict = {}
    ev._build_wikidata(tmp_path / "acquired", tmp_path / "o", manifest)
    lines = (tmp_path / "o" / "wikidata_entities" / "items.jsonl").read_text().splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["Q40", "Q50"]
    assert lines[0].startswith('{"a": 2, "claims"') and lines[0].endswith('"z": 1}')  # keys sorted
    view = manifest["wikidata_entities"]
    assert (
        view["sampling"]["identifiers_absent"] == 1
        and view["sampling"]["people_dropped"] == 1
        and view["sampling"]["request_files"] == 2
    )
    assert view["files"]["items.jsonl"]["rows"] == 2 and view["dropped"] == [
        "items that are instances of human"
    ]
    assert view["source_snapshot"] == f"wikidata_entities/{SNAP}"


# --- Grid-scale battery systems ----------------------------------------------------------------------  # noqa: E501


def _bess_frame():
    return pd.DataFrame(
        {
            "HoursElapsed": [1.0, 0.0, 0.0, None], "DayNumber": [0, 0, 0, 1],
            "Meter": ["PDC", "PDC", "PAC", "PAC"], "Power": [0.5, 0.1, 0.2, 0.3],
            "RequestedPower": [None, None, 0.2, 0.3], "ReactivePower": [None] * 4,
            "RequestedReactivePower": [None] * 4, "Voltage": [3.3, 3.2, None, None],
            "VoltageMax": [None] * 4, "VoltageMin": [None] * 4, "VoltageAvg": [3.3, 3.2, None, None],  # noqa: E501
            "Current": [0.1, 0.0, None, None], "SOC": [0.9, 0.8, None, None],
            "TempMax": [None] * 4, "TempMin": [None] * 4, "TempAvg": [25.0, 24.0, None, None],
            "TempAmbient": [None] * 4, "QualityFlag": [False, True, False, False],
            "CycleIndex": ["0Out", "1", "0Out", "2"], "Use": [True, False, True, True],
        }
    )  # fmt: skip


def test_bess_view_keeps_missing_channels_and_flags_in_elapsed_time_order():
    out = ev.bess_view(_bess_frame(), "SYS")
    assert list(out.columns) == list(ev.BESS_COLUMNS) and ev.BESS_COLUMNS[:3] == (
        "system",
        "meter",
        "hours_elapsed",
    )
    assert len(out) == 3 and set(out["system"]) == {
        "SYS"
    }  # the row without elapsed time is dropped
    assert out[["hours_elapsed", "meter"]].values.tolist() == [
        [0.0, "PAC"],
        [0.0, "PDC"],
        [1.0, "PDC"],
    ]
    assert out["voltage"].isna().tolist() == [True, False, False] and out["soc"].iloc[2] == 0.9
    assert (
        out["quality_flag"].tolist() == [False, True, False] and out["quality_flag"].dtype == bool
    )
    assert out["cycle_index"].tolist() == ["0Out", "1", "0Out"] and out["use"].tolist() == [
        True,
        False,
        True,
    ]
    with pytest.raises(ev.ViewError, match="columns not found: .*SOC"):
        ev.bess_view(_bess_frame().drop(columns=["SOC"]), "SYS")


def test_the_bess_builder_stacks_the_system_files_and_refuses_an_empty_snapshot(tmp_path):
    import pyarrow as _pa
    import pyarrow.feather as _fe

    raw = tmp_path / "acquired" / "zen_bess" / SNAP / "raw"
    raw.mkdir(parents=True)
    with pytest.raises(ev.ViewError, match="no feather file in the snapshot"):
        ev._build_bess(tmp_path / "acquired", tmp_path / "o", {})
    for name in ("B_SYS", "A_SYS"):
        _fe.write_feather(
            _pa.Table.from_pandas(_bess_frame(), preserve_index=False), raw / f"{name}.feather"
        )
    manifest: dict = {}
    ev._build_bess(tmp_path / "acquired", tmp_path / "o", manifest)
    out = pd.read_csv(tmp_path / "o" / "zen_bess" / "readings.csv")
    assert out["system"].tolist() == ["A_SYS"] * 3 + ["B_SYS"] * 3
    view = manifest["zen_bess"]
    assert view["sampling"]["systems"] == ["A_SYS", "B_SYS"] and view["sampling"]["rows_in"] == 6
    assert (
        view["files"]["readings.csv"]["rows"] == 6 and view["source_snapshot"] == f"zen_bess/{SNAP}"
    )


# --- CARE to Compare, Wind Farm B -------------------------------------------------------------------  # noqa: E501


def _zip_local(name, content, method=8):
    import struct as _st
    import zlib as _zl

    if method == 8:
        packer = _zl.compressobj(wbits=-15)
        body = packer.compress(content) + packer.flush()
    else:
        body = content
    header = b"PK\x03\x04" + _st.pack(
        "<HHHHHIIIHH", 20, 0, method, 0, 0, 0, len(body), len(content), len(name), 0
    )
    return header + name.encode() + body


def _care_frame(rows=3):
    data = {
        "time_stamp": ["2023-01-01 00:20:00", "2023-01-01 00:00:00", "2023-01-01 00:10:00"][:rows],
        "asset_id": [7] * rows, "id": [3, 1, 2][:rows], "train_test": ["train", "train", "prediction"][:rows],  # noqa: E501
        "status_type_id": [0, 2, 4][:rows], "sensor_0_avg": [1.5, None, 3.0][:rows], "sensor_0_max": [9.0] * rows,  # noqa: E501
        "sensor_1_avg": ["x", "2", "3"][:rows], "sensor_1_std": [0.1] * rows,
    }  # fmt: skip
    return pd.DataFrame(data)


def test_zip_local_member_reads_a_deflated_member_and_refuses_damaged_or_unsupported_ones():
    content = b"a;b\n1;2\n" * 50
    assert ev.zip_local_member(_zip_local("m.csv", content) + b"PK\x03\x04next") == content
    with pytest.raises(ev.ViewError, match="^unsupported zip method 0$"):
        ev.zip_local_member(_zip_local("m.csv", b"x", method=0))
    with pytest.raises(ev.ViewError, match="^not a zip local header$"):
        ev.zip_local_member(b"PK\x01\x02" + b"\0" * 40)
    with pytest.raises(ev.ViewError, match="^not a zip local header$"):
        ev.zip_local_member(b"PK\x03\x04")
    cut = _zip_local("m.csv", content)[:-8]
    with pytest.raises(ev.ViewError, match="^deflate stream incomplete$"):
        ev.zip_local_member(cut)
    with pytest.raises(ev.ViewError, match="^member larger than the limit$"):
        ev.zip_local_member(_zip_local("m.csv", content), max_out=10)
    assert (
        ev.zip_local_member(_zip_local("m.csv", b"x" * 10), max_out=10) == b"x" * 10
    )  # exactly at the limit


def test_care_view_keeps_the_average_sensors_status_and_phase_and_orders_by_time():
    out = ev.care_series_view(_care_frame(), 34)
    assert list(out.columns) == [*ev.CARE_META, "sensor_0_avg", "sensor_1_avg"]
    assert out["event_id"].tolist() == [34, 34, 34] and out["row_id"].tolist() == [1, 2, 3]
    assert out["train_test"].tolist() == ["train", "prediction", "train"] and out[
        "status_type"
    ].tolist() == [2, 4, 0]
    assert out["sensor_0_avg"].isna().tolist() == [True, False, False]
    assert out["sensor_1_avg"].iloc[:2].tolist() == [2.0, 3.0] and pd.isna(
        out["sensor_1_avg"].iloc[2]
    )  # "x" is unreadable
    assert out["asset_id"].tolist() == [7, 7, 7] and out["time_stamp"].is_monotonic_increasing
    for gone in ("sensor_0_max", "sensor_1_std"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="^columns not found: \\['status_type_id'\\]$"):
        ev.care_series_view(_care_frame().drop(columns=["status_type_id"]), 1)
    with pytest.raises(ev.ViewError, match="^no average sensor columns$"):
        ev.care_series_view(
            _care_frame()[["time_stamp", "asset_id", "id", "train_test", "status_type_id"]], 1
        )
    bad = _care_frame()
    bad.loc[0, "time_stamp"] = "not a time"
    assert len(ev.care_series_view(bad, 1)) == 2  # a row without a readable time is dropped


def _care_snapshot(root, ids=(5, 2, 3)):
    raw = root / "zen_care_wind_b" / ev.CARE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    info = "asset_id;event_id;event_label;event_start;event_start_id;event_end;event_end_id;event_description\n"  # noqa: E501
    info += "7;5;anomaly;2023-01-01 00:00:00;1;2023-01-02 00:00:00;2;high temperature\n"
    info += "8;2;normal;2023-01-01 00:00:00;1;2023-01-02 00:00:00;2;\n"
    info += "9;9;normal;2023-01-01 00:00:00;1;2023-01-02 00:00:00;2;\n"
    info += "8;3;normal;2023-01-01 00:00:00;1;2023-01-02 00:00:00;2;\n"
    (raw / "event_info.csv").write_bytes(_zip_local("info", info.encode()))
    for event_id in ids:
        csv_text = _care_frame().assign(asset_id=event_id).to_csv(sep=";", index=False)
        (raw / f"{event_id}.csv").write_bytes(_zip_local(f"{event_id}.csv", csv_text.encode()))


def test_the_care_builder_stacks_the_datasets_and_keeps_the_natural_labels_in_a_separate_file(
    tmp_path,
):
    _care_snapshot(tmp_path / "acquired")
    (
        tmp_path
        / "acquired"
        / "zen_care_wind_b"
        / ev.CARE_SNAPSHOT
        / "raw"
        / "feature_description.csv"
    ).write_bytes(b"x")
    manifest: dict = {}
    ev._build_care(tmp_path / "acquired", tmp_path / "o", manifest)
    folder = tmp_path / "o" / "zen_care_wind_b"
    series = pd.read_csv(folder / "series.csv")
    assert (
        series["event_id"].tolist() == [2] * 3 + [3] * 3 + [5] * 3
    )  # datasets in identifier order
    assert "event_label" not in series and "event_description" not in series
    events = pd.read_csv(folder / "events.csv")
    assert events["event_id"].tolist() == [2, 3, 5, 9]
    assert events["in_view"].tolist() == [True, True, True, False]
    assert events["event_label"].tolist() == ["normal", "normal", "anomaly", "normal"]
    view = manifest["zen_care_wind_b"]
    assert (
        view["sampling"]["datasets"] == [2, 3, 5]
        and view["sampling"]["anomaly_datasets_in_view"] == 1
    )
    assert view["sampling"]["rows_in"] == 9 and view["files"]["events.csv"]["rows"] == 4
    assert (
        view["source_snapshot"] == f"zen_care_wind_b/{ev.CARE_SNAPSHOT}"
        and view["pseudonymised"] == []
    )


def test_the_care_builder_refuses_a_snapshot_without_datasets(tmp_path):
    _care_snapshot(tmp_path / "acquired", ids=())
    with pytest.raises(ev.ViewError, match="^no dataset in the snapshot$"):
        ev._build_care(tmp_path / "acquired", tmp_path / "o", {})


def test_zip_local_member_header_boundaries_extra_field_and_wide_name_lengths():
    import struct as _st

    bare = b"PK\x03\x04" + b"\0" * 26  # exactly 30 bytes: a header with nothing after it
    assert len(bare) == 30
    with pytest.raises(ev.ViewError, match="^unsupported zip method 0$"):
        ev.zip_local_member(bare)
    deflate_header = bytearray(bare)
    deflate_header[8:10] = _st.pack("<H", 8)
    with pytest.raises(ev.ViewError, match="^deflate stream incomplete$"):
        ev.zip_local_member(bytes(deflate_header))
    body = _zip_local("n.csv", b"data;1\n")
    head, rest = body[:30], body[30:]
    wide = bytearray(head)
    wide[28:30] = _st.pack("<H", 6)  # extra field of six bytes between name and data
    padded = bytes(wide) + rest[:5] + b"ABCDEF" + rest[5:]
    assert ev.zip_local_member(padded) == b"data;1\n"
    long_name = "n" * 40000  # above the signed 16-bit range
    assert ev.zip_local_member(_zip_local(long_name, b"abc")) == b"abc"


def test_care_view_turns_unreadable_ids_and_status_into_missing_and_orders_equal_times_by_file_order():  # noqa: E501
    raw = _care_frame().astype({"asset_id": object, "id": object, "status_type_id": object})
    raw.loc[0, ["asset_id", "id", "status_type_id"]] = ["x", "y", "z"]
    out = ev.care_series_view(raw, 1)
    last = out.iloc[-1]
    assert pd.isna(last["asset_id"]) and pd.isna(last["row_id"]) and pd.isna(last["status_type"])
    n = 40
    tied = pd.DataFrame(
        {
            "time_stamp": ["2023-01-01 00:00:00"] * n,
            "asset_id": 1,
            "id": range(n),
            "train_test": "train",
            "status_type_id": 0,
            "s_avg": range(n),
        }
    )
    assert ev.care_series_view(tied, 1)["row_id"].tolist() == list(range(n))


# --- NVD CVE records ---------------------------------------------------------------------------------  # noqa: E501


def _nvd_page(ids, total=None, **extra):
    records = [
        {"cve": {"id": i, "descriptions": [{"lang": "en", "value": i}], **extra}} for i in ids
    ]
    return {"totalResults": len(records) if total is None else total, "vulnerabilities": records}


def test_nvd_view_orders_by_identifier_keeps_the_first_of_a_repeated_identifier_and_counts_repeats():  # noqa: E501
    first = _nvd_page(["CVE-2022-0002", "CVE-2018-0001"], extra_tag="first")
    second = _nvd_page(["CVE-2022-0002", "CVE-2020-0003"], extra_tag="second")
    view, repeated = ev.nvd_view([first, second])
    assert [r["id"] for r in view] == [
        "CVE-2018-0001",
        "CVE-2020-0003",
        "CVE-2022-0002",
    ] and repeated == 1
    assert view[2]["extra_tag"] == "first" and view[0]["descriptions"][0]["lang"] == "en"
    assert ev.nvd_view([]) == ([], 0)


def test_the_nvd_builder_records_completeness_writes_the_required_notice_and_refuses_an_empty_snapshot(  # noqa: E501
    tmp_path,
):
    raw = tmp_path / "acquired" / "nvd_cve" / ev.NVD_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with pytest.raises(ev.ViewError, match="^no NVD page in the snapshot$"):
        ev._build_nvd(tmp_path / "acquired", tmp_path / "o", {})
    (raw / "cves_b.json").write_text(json.dumps(_nvd_page(["CVE-2020-1"], total=5)))
    (raw / "cves_a.json").write_text(json.dumps(_nvd_page(["CVE-2018-1", "CVE-2018-2"])))
    manifest: dict = {}
    ev._build_nvd(tmp_path / "acquired", tmp_path / "o", manifest)
    folder = tmp_path / "o" / "nvd_cve"
    lines = (folder / "cves.jsonl").read_text().splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["CVE-2018-1", "CVE-2018-2", "CVE-2020-1"]
    assert lines[0].startswith('{"descriptions"')  # keys sorted
    notice = (folder / "NOTICE.txt").read_text()
    assert (
        notice == ev.NVD_NOTICE + "\n"
        and "MITRE" in notice
        and "not endorsed or certified by the NVD" in notice
    )
    sampling = manifest["nvd_cve"]["sampling"]
    assert sampling["pages"] == ["cves_a.json", "cves_b.json"] and sampling["total_results"] == [
        2,
        5,
    ]
    assert sampling["complete_pages"] is False and sampling["repeated_ids"] == 0
    assert (
        manifest["nvd_cve"]["files"]["cves.jsonl"]["rows"] == 3
        and manifest["nvd_cve"]["source_snapshot"] == f"nvd_cve/{ev.NVD_SNAPSHOT}"
    )


# --- St. Gallen smart factory ------------------------------------------------------------------------  # noqa: E501


def _unisg_messages():
    base = {
        "current_state": "ready",
        "current_task": "",
        "current_task_duration": 0.0,
        "current_sub_task": "",
    }
    return [
        {"id": "u3", "station": "VGR_1", "timestamp": "2023-04-11 09:57:48.75", "i1_pos": 1, **base},  # noqa: E501
        {"id": "u1", "station": "MM_1", "timestamp": "2023-04-11 09:57:48.72", "m1_speed": 0, **base},  # noqa: E501
        {"id": "u2", "station": "EC_1", "timestamp": "2023-04-11 09:57:48.72", "i3_photo": "x", **base, "current_task_duration": "n/a"},  # noqa: E501
        {"id": "u4", "station": "MM_1", "timestamp": "bad", "m1_speed": 5, **base},
    ]  # fmt: skip


def _unisg_activities():
    def act(i, pi, name, start, canceled=False):
        return {
            "processInstanceId": pi,
            "processDefinitionKey": "storage",
            "activityName": name,
            "activityType": "serviceTask",
            "startTime": start,
            "endTime": start,
            "durationInMillis": i,
            "canceled": canceled,
        }  # noqa: E501

    return [
        act(5, "p2", "B", "2023-04-11T10:00:05.000+0200"),
        act(1, "p1", "A", "2023-04-11T10:00:01.000+0200", True),
        act(2, "p9", "C", "2023-04-11T10:00:05.000+0200"),
    ]  # noqa: E501


def test_unisg_sensor_view_keeps_station_columns_drops_ids_and_orders_by_time_and_station():
    out = ev.unisg_sensor_view(_unisg_messages())
    assert list(out.columns) == [*ev.UNISG_HEAD, "i1_pos", "i3_photo", "m1_speed"]
    assert (
        out["station"].tolist() == ["EC_1", "MM_1", "VGR_1"] and len(out) == 3
    )  # the unreadable time is dropped
    assert out["m1_speed"].isna().tolist() == [True, False, True] and out[
        "i1_pos"
    ].isna().tolist() == [True, True, False]
    assert out["i3_photo"].isna().all() and pd.isna(out["current_task_duration"].iloc[0])
    assert "id" not in out and out["timestamp"].is_monotonic_increasing
    with pytest.raises(ev.ViewError, match="^column 'current_state' not found$"):
        ev.unisg_sensor_view([{"station": "A", "timestamp": "2023-04-11 09:57:48.72"}])


def test_unisg_activity_view_joins_the_process_state_and_orders_by_start_then_instance():
    out = ev.unisg_activity_view(
        _unisg_activities(),
        [{"id": "p1", "state": "COMPLETED"}, {"id": "p2", "state": "EXTERNALLY_TERMINATED"}],
    )
    assert list(out.columns) == list(ev.UNISG_ACTIVITY_COLUMNS)
    assert out["process_instance"].tolist() == ["p1", "p2", "p9"]
    assert out["process_state"].tolist()[:2] == ["COMPLETED", "EXTERNALLY_TERMINATED"] and pd.isna(
        out["process_state"].iloc[2]
    )
    assert out["canceled"].tolist() == [True, False, False] and out["canceled"].dtype == bool
    assert out["start_time"].is_monotonic_increasing and str(out["start_time"].dtype).endswith(
        "UTC]"
    )
    assert out["duration_ms"].tolist() == [1, 5, 2] and out["activity_name"].tolist() == [
        "A",
        "B",
        "C",
    ]
    assert list(ev.unisg_activity_view([], []).columns) == list(ev.UNISG_ACTIVITY_COLUMNS)


def _unisg_snapshot(root):
    raw = root / "zen_unisg_factory" / ev.UNISG_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    lines = [json.dumps(m) for m in _unisg_messages()] + ["{broken"]
    (raw / ev.UNISG_LOG).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (raw / "camunda-activity.json").write_text(json.dumps(_unisg_activities()), encoding="utf-8")
    (raw / "camunda-process.json").write_text(
        json.dumps([{"id": "p1", "state": "COMPLETED"}]), encoding="utf-8"
    )


def test_the_unisg_builder_writes_both_views_and_records_what_it_read(tmp_path):
    _unisg_snapshot(tmp_path / "acquired")
    manifest: dict = {}
    ev._build_unisg(tmp_path / "acquired", tmp_path / "o", manifest)
    folder = tmp_path / "o" / "zen_unisg_factory"
    assert (
        len(pd.read_csv(folder / "sensors.csv")) == 3
        and len(pd.read_csv(folder / "activities.csv")) == 3
    )
    view = manifest["zen_unisg_factory"]
    assert view["sampling"]["messages"] == 4 and view["sampling"]["unreadable_lines"] == 1
    assert view["sampling"]["stations"] == ["EC_1", "MM_1", "VGR_1"]
    assert (
        view["sampling"]["activity_instances"] == 3 and view["sampling"]["process_instances"] == 1
    )
    assert (
        view["files"]["sensors.csv"]["rows"] == 3 and view["files"]["activities.csv"]["rows"] == 3
    )
    assert (
        view["dropped"] == ["message identifiers"]
        and view["source_snapshot"] == f"zen_unisg_factory/{ev.UNISG_SNAPSHOT}"
    )


def test_unisg_views_keep_every_value_and_coerce_unreadable_ones():
    out = ev.unisg_sensor_view(
        _unisg_messages()
        + [
            {
                "station": "WT_1",
                "timestamp": "2023-04-11 09:57:49.00",
                "current_state": "ready",
                "current_task": "t",
                "current_task_duration": 2.5,
                "current_sub_task": "",
            }
        ]
    )
    assert (
        out["current_task_duration"].dtype == "float64"
        and out["current_task_duration"].iloc[-1] == 2.5
    )
    assert out["current_task_duration"].isna().tolist() == [
        True,
        False,
        False,
        False,
    ]  # only the unreadable text
    acts = _unisg_activities()
    acts[1]["endTime"] = "not a time"
    acts[2]["durationInMillis"] = "slow"
    out = ev.unisg_activity_view(acts, [{"id": "p1", "state": "COMPLETED"}])
    assert (
        out["process_key"].tolist() == ["storage"] * 3
        and out["activity_type"].tolist() == ["serviceTask"] * 3
    )
    assert out["end_time"].isna().tolist() == [True, False, False] and str(
        out["end_time"].dtype
    ).endswith("UTC]")
    assert out["duration_ms"].isna().tolist() == [False, False, True]
    assert out["end_time"].iloc[1].tzinfo is not None
    bad_start = _unisg_activities()
    bad_start[0]["startTime"] = "never"
    assert ev.unisg_activity_view(bad_start, [])["start_time"].isna().sum() == 1


def test_the_unisg_builder_counts_every_unreadable_line_and_reads_utf8_whatever_the_locale(
    tmp_path,
):
    _unisg_snapshot(tmp_path / "acquired")
    raw = tmp_path / "acquired" / "zen_unisg_factory" / ev.UNISG_SNAPSHOT / "raw"
    acts = _unisg_activities()
    acts[0]["activityName"] = "Pr\u00e9parer \u00b0C"
    (raw / "camunda-activity.json").write_bytes(
        json.dumps(acts, ensure_ascii=False).encode("utf-8")
    )
    log = (raw / ev.UNISG_LOG).read_bytes().decode("utf-8")
    (raw / ev.UNISG_LOG).write_bytes((log + "{also broken\n").encode("utf-8"))
    manifest: dict = {}
    ev._build_unisg(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["zen_unisg_factory"]["sampling"]["unreadable_lines"] == 2
    names = pd.read_csv(tmp_path / "o" / "zen_unisg_factory" / "activities.csv")[
        "activity_name"
    ].tolist()
    assert "Pr\u00e9parer \u00b0C" in names


def _care_a_snapshot(root):
    raw = root / "zen_care_wind_a" / ev.CARE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    info = "asset;event_id;event_label;event_start;event_start_id;event_end;event_end_id;event_description\n"  # noqa: E501
    info += "7;5;anomaly;2023-01-01 00:00:00;1;2023-01-02 00:00:00;2;Gearbox failure\n"
    (raw / "event_info.csv").write_bytes(_zip_local("info", info.encode()))
    frame = _care_frame().assign(asset_id=7)
    (raw / "5.csv").write_bytes(_zip_local("5.csv", frame.to_csv(sep=";", index=False).encode()))


def test_the_care_farm_a_builder_uses_its_own_folder_name_and_method(tmp_path):
    _care_a_snapshot(tmp_path / "acquired")
    manifest: dict = {}
    ev._build_care_a(tmp_path / "acquired", tmp_path / "o", manifest)
    assert (
        list(manifest) == ["zen_care_wind_a"]
        and (tmp_path / "o" / "zen_care_wind_a" / "series.csv").exists()
    )
    view = manifest["zen_care_wind_a"]
    assert view["sampling"]["method"].startswith("eight of the 22 datasets of Wind Farm A")
    assert view["sampling"]["anomaly_datasets_in_view"] == 1
    assert view["source_snapshot"] == f"zen_care_wind_a/{ev.CARE_SNAPSHOT}"
    assert pd.read_csv(tmp_path / "o" / "zen_care_wind_a" / "events.csv")["in_view"].tolist() == [
        True
    ]


# --- PBDB relational view ----------------------------------------------------------------------------  # noqa: E501


def _taxa(rows):
    return pd.DataFrame(rows, columns=["taxon_no", "parent_no"])


def test_taxon_closure_follows_parents_once_and_counts_ancestors_missing_from_the_source():
    taxa = _taxa([(1, None), (2, 1), (3, 2), (4, 2), (5, 99), (6, 7), (7, 6), (8, 1)])
    kept, absent = ev.taxon_closure(taxa, {3, 5})
    assert kept["taxon_no"].tolist() == [1, 2, 3, 5] and absent == 1  # 99 is not in the source
    kept, absent = ev.taxon_closure(taxa, {6})
    assert kept["taxon_no"].tolist() == [6, 7] and absent == 0  # a cycle ends the walk
    kept, absent = ev.taxon_closure(taxa, {1000})
    assert kept.empty and absent == 0  # an unknown needed identifier selects nothing
    kept, _ = ev.taxon_closure(taxa, {4, 3})
    assert kept["taxon_no"].tolist() == [1, 2, 3, 4] and kept.index.tolist() == [0, 1, 2, 3]


def _pbdb_rel_snapshot(root, tmp):
    import zipfile

    import pyarrow as _pa
    import pyarrow.parquet as _pq

    raw = root / "zen_pbdb" / SNAP / "raw"
    raw.mkdir(parents=True)
    occ = pd.DataFrame({c: [None] * 4 for c in ev.PBDB_REL_OCC})
    occ["occurrence_no"] = [4, 3, 2, 1]
    occ["accepted_no"] = [30, 30, 50, None]
    taxa = pd.DataFrame({c: [None] * 5 for c in ev.PBDB_REL_TAXA})
    taxa["taxon_no"] = [30, 20, 10, 50, 60]
    taxa["parent_no"] = [20, 10, 99, 10, 10]
    for name, frame, zip_name in (
        ("occ", occ, "pbdb_parquet.zip"),
        ("taxa", taxa, "pbdb_taxa_parquet.zip"),
    ):
        _pq.write_table(_pa.Table.from_pandas(frame, preserve_index=False), tmp / f"{name}.parquet")
        with zipfile.ZipFile(raw / zip_name, "w") as z:
            z.write(tmp / f"{name}.parquet", f"{name}.parquet")


def test_the_pbdb_relational_builder_keeps_the_referenced_taxa_and_records_the_relations(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ev, "PBDB_STRIDE", 1)
    _pbdb_rel_snapshot(tmp_path / "acquired", tmp_path)
    manifest: dict = {}
    ev._build_pbdb_relational(tmp_path / "acquired", tmp_path / "o", manifest)
    folder = tmp_path / "o" / "zen_pbdb_relational"
    occ = pd.read_csv(folder / "occurrences.csv")
    taxa = pd.read_csv(folder / "taxa.csv")
    assert occ["occurrence_no"].tolist() == [1, 2, 3, 4] and taxa["taxon_no"].tolist() == [
        10,
        20,
        30,
        50,
    ]
    assert (
        60 not in taxa["taxon_no"].tolist()
    )  # not named by a sampled occurrence and not an ancestor
    view = manifest["zen_pbdb_relational"]
    sampling = view["sampling"]
    assert sampling["relations"] == [
        ["occurrences", "accepted_no", "taxa", "taxon_no"],
        ["taxa", "parent_no", "taxa", "taxon_no"],
    ]
    assert (
        sampling["occurrences_without_taxon"] == 1
        and sampling["occurrences_with_unknown_taxon"] == 0
    )
    assert sampling["ancestors_absent_from_source"] == 1 and sampling["taxa_in_source"] == 5
    assert sampling["occurrences_rows_read"] == 4 and view["source_snapshot"] == f"zen_pbdb/{SNAP}"
    assert view["files"]["occurrences.csv"]["rows"] == 4 and view["files"]["taxa.csv"]["rows"] == 4


def _pbdb_rel_snapshot_extra(root, tmp):
    import zipfile

    import pyarrow as _pa
    import pyarrow.parquet as _pq

    taxa = pd.DataFrame({c: [None] * 3 for c in ev.PBDB_REL_TAXA})
    taxa["taxon_no"] = [30, 20, 50]
    taxa["parent_no"] = [20, 50, None]
    _pq.write_table(_pa.Table.from_pandas(taxa, preserve_index=False), tmp / "taxa_extra.parquet")
    with zipfile.ZipFile(root / "zen_pbdb" / SNAP / "raw" / "pbdb_taxa_parquet.zip", "w") as z:
        z.write(tmp / "taxa_extra.parquet", "taxa.parquet")


def test_jolpica_spec_declares_tables_keys_and_a_snapshot_and_hides_persons():
    spec = ev.TABLE_SETS["jolpica_f1"]
    assert spec["snapshot"] == "2026-11-22" and spec["archive"]["file"] == "jolpica-f1-csv.zip"
    for child, child_key, parent, parent_key in spec["relations"]:
        assert (
            child_key in spec["tables"][child]["keep"]
            and parent_key in spec["tables"][parent]["keep"]
        )
    kept = {c for t in spec["tables"].values() for c in t["keep"]}
    assert not kept & {
        "forename",
        "surname",
        "date_of_birth",
        "nationality_driver",
        "wikipedia",
        "api_id",
    }
    assert spec["tables"]["formula_one_driver"]["keep"] == ["id", "permanent_car_number"]


def test_a_table_set_with_its_own_snapshot_is_read_from_that_snapshot_and_recorded(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "src" / "2030-01-01" / "raw"
    raw.mkdir(parents=True)
    _w(raw / "t.csv", "k,v\n1,a\n2,b\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"src": {"snapshot": "2030-01-01", "sep": ",", "quote_none": False, "dropped": [], "tables": {"t": {"keep": ["k", "v"]}}, "relations": []}})  # fmt: skip  # noqa: E501
    manifest: dict = {}
    ev._build_tables(root, tmp_path / "o", manifest)
    assert (
        manifest["src"]["source_snapshot"] == "src/2030-01-01"
        and manifest["src"]["files"]["t.csv"]["rows"] == 2
    )


# --- Backblaze Drive Stats ---------------------------------------------------------------------------  # noqa: E501


def _serials():
    kept = [
        s
        for s in (f"S{i}" for i in range(200))
        if int(ev.pseudonym(s), 16) % ev.BACKBLAZE_MODULO == 0
    ]
    skipped = [
        s
        for s in (f"S{i}" for i in range(200))
        if int(ev.pseudonym(s), 16) % ev.BACKBLAZE_MODULO != 0
    ]
    return kept, skipped


def _bb_day(day, serials, failed=()):
    rows = [
        {
            "date": day,
            "serial_number": s,
            "model": "M1",
            "capacity_bytes": "3000",
            "failure": "1" if s in failed else "0",
            "smart_9_raw": "15",
            "smart_1_normalized": "bad" if s == serials[0] else "100",
        }
        for s in serials
    ]  # noqa: E501
    return pd.DataFrame(rows)


def test_backblaze_view_keeps_one_drive_in_eight_with_its_whole_series_pseudonymised():
    kept, skipped = _serials()
    frames = [
        _bb_day("2014-01-02", [kept[0], kept[1], skipped[0]], failed={kept[1]}),
        _bb_day("2014-01-01", [kept[0], kept[1], skipped[1]]),
    ]
    out = ev.backblaze_view(frames)
    assert list(out.columns) == [
        "date",
        "drive",
        "model",
        "capacity_bytes",
        "failure",
        "smart_1_normalized",
        "smart_9_raw",
    ]
    assert len(out) == 4 and set(out["drive"]) == {ev.pseudonym(kept[0]), ev.pseudonym(kept[1])}
    assert (
        out["date"].is_monotonic_increasing is False
        and out.groupby("drive")["date"].apply(lambda d: d.is_monotonic_increasing).all()
    )
    assert (
        out["failure"].sum() == 1
        and out["failure"].dtype.kind in "if"
        and out["capacity_bytes"].iloc[0] == 3000
    )
    assert (
        out["smart_1_normalized"].isna().sum() == 2 and "serial_number" not in out
    )  # the unreadable value is missing
    with pytest.raises(ev.ViewError, match="^columns not found: \\['failure'\\]$"):
        ev.backblaze_view([_bb_day("2014-01-01", kept[:1]).drop(columns=["failure"])])
    bad = _bb_day("not a date", kept[:1])
    assert ev.backblaze_view([bad]).empty


def _bb_zip(root, days=3):
    import zipfile as _z

    kept, skipped = _serials()
    raw = root / "backblaze_drive_stats" / ev.BACKBLAZE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with _z.ZipFile(raw / "data_2014.zip", "w") as z:
        for d in range(days, 0, -1):
            day = f"2014-01-0{d}"
            z.writestr(
                f"2014/{day}.csv",
                _bb_day(
                    day, [kept[0], kept[1], skipped[0]], failed={kept[1]} if d == 2 else ()
                ).to_csv(index=False),
            )
        z.writestr("__MACOSX/2014/._2014-01-01.csv", "x")
        z.writestr("2014/readme.txt", "x")


def test_the_backblaze_builder_uses_the_first_daily_files_and_records_failures(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ev, "BACKBLAZE_DAYS", 2)
    _bb_zip(tmp_path / "acquired")
    manifest: dict = {}
    ev._build_backblaze(tmp_path / "acquired", tmp_path / "o", manifest)
    out = pd.read_csv(tmp_path / "o" / "backblaze_drive_stats" / "drive_days.csv")
    assert sorted(set(out["date"])) == ["2014-01-01", "2014-01-02"] and len(out) == 4
    view = manifest["backblaze_drive_stats"]
    assert (
        view["sampling"]["days"] == ["2014/2014-01-01.csv", "2014/2014-01-02.csv"]
        and view["sampling"]["day_files"] == 2
    )
    assert view["sampling"]["drives"] == 2 and view["sampling"]["failures"] == 1
    assert view["pseudonymised"] == ["drive"] and view["salt_label"] == ev.SALT
    assert (
        view["source_snapshot"] == f"backblaze_drive_stats/{ev.BACKBLAZE_SNAPSHOT}"
        and view["files"]["drive_days.csv"]["rows"] == 4
    )


def test_the_backblaze_builder_refuses_an_archive_without_daily_files(tmp_path):
    import zipfile as _z

    raw = tmp_path / "acquired" / "backblaze_drive_stats" / ev.BACKBLAZE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with _z.ZipFile(raw / "data_2014.zip", "w") as z:
        z.writestr("2014/readme.txt", "x")
    with pytest.raises(ev.ViewError, match="^no daily file in the archive$"):
        ev._build_backblaze(tmp_path / "acquired", tmp_path / "o", {})


def test_the_backblaze_builder_reports_the_last_chosen_day_and_passes_the_extraction_limits(
    tmp_path, monkeypatch
):
    import acquisition as _aq

    seen = []
    real = _aq.extract_member
    monkeypatch.setattr(_aq, "extract_member", lambda *a, **k: seen.append(k) or real(*a, **k))
    monkeypatch.setattr(ev, "BACKBLAZE_DAYS", 3)
    _bb_zip(tmp_path / "acquired")
    manifest: dict = {}
    ev._build_backblaze(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["backblaze_drive_stats"]["sampling"]["days"] == [
        "2014/2014-01-01.csv",
        "2014/2014-01-03.csv",
    ]
    assert manifest["backblaze_drive_stats"]["sampling"]["day_files"] == 3
    assert seen == [{"max_bytes": 1 << 28, "max_ratio": 100}] * 3


# --- NYC yellow taxi trips ---------------------------------------------------------------------------  # noqa: E501


def _tlc_page(rows):
    base = {c: "1" for c in ev.TLC_COLUMNS}
    base.update(
        {
            "store_and_fwd_flag": "N",
            "tpep_pickup_datetime": "2023-03-07T08:00:00.000",
            "tpep_dropoff_datetime": "2023-03-07T08:10:00.000",
            "total_amount": "10.5",
        }
    )  # noqa: E501
    return pd.DataFrame([{**base, **r} for r in rows])


def test_taxi_view_keeps_every_trip_with_its_amounts_codes_and_order():
    page_a = _tlc_page(
        [
            {
                "tpep_pickup_datetime": "2023-03-07T09:00:00.000",
                "total_amount": "-5.0",
                "payment_type": "4",
            },
            {
                "tpep_pickup_datetime": "2023-03-07T07:00:00.000",
                "total_amount": "0.0",
                "passenger_count": "0.0",
            },
        ]
    )  # noqa: E501
    page_b = _tlc_page(
        [
            {
                "tpep_pickup_datetime": "2023-03-07T08:00:00.000",
                "fare_amount": "bad",
                "vendorid": "x",
                "store_and_fwd_flag": "Y",
            },
            {"tpep_pickup_datetime": "not a time"},
        ]
    )  # noqa: E501
    out = ev.taxi_trip_view([page_a, page_b])
    assert (
        list(out.columns) == list(ev.TLC_COLUMNS) and len(out) == 3
    )  # the unreadable pickup is dropped
    assert out["tpep_pickup_datetime"].is_monotonic_increasing and out["total_amount"].tolist() == [
        0.0,
        10.5,
        -5.0,
    ]
    assert str(out["payment_type"].dtype) == "Int64" and out["payment_type"].tolist() == [1, 1, 4]
    assert out["fare_amount"].isna().tolist() == [False, True, False] and pd.isna(
        out["vendorid"].iloc[1]
    )
    assert (
        out["store_and_fwd_flag"].tolist() == ["N", "Y", "N"]
        and out["passenger_count"].iloc[0] == 0.0
    )
    assert (
        out["tpep_dropoff_datetime"].dtype.kind == "M" and out["trip_distance"].dtype == "float64"
    )
    with pytest.raises(ev.ViewError, match="^columns not found: \\['airport_fee'\\]$"):
        ev.taxi_trip_view([_tlc_page([{}]).drop(columns=["airport_fee"])])


def test_the_tlc_builder_reads_every_page_and_records_days_and_unusual_fares(tmp_path):
    raw = tmp_path / "acquired" / "nyc_tlc_yellow" / ev.TLC_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with pytest.raises(ev.ViewError, match="^no trip page in the snapshot$"):
        ev._build_tlc(tmp_path / "acquired", tmp_path / "o", {})
    _tlc_page(
        [
            {"tpep_pickup_datetime": "2023-03-07T10:00:00.000"},
            {"tpep_pickup_datetime": "2023-03-07T11:00:00.000", "total_amount": "0.0"},
        ]
    ).to_csv(raw / "yellow_2023-03-07_p0.csv", index=False)
    _tlc_page(
        [
            {"tpep_pickup_datetime": "2023-03-11T10:00:00.000", "total_amount": "-1.0"},
            {"tpep_pickup_datetime": "bad"},
        ]
    ).to_csv(raw / "yellow_2023-03-11_p0.csv", index=False)
    manifest: dict = {}
    ev._build_tlc(tmp_path / "acquired", tmp_path / "o", manifest)
    view = manifest["nyc_tlc_yellow"]
    assert view["sampling"]["rows_by_day"] == {"2023-03-07": 2, "2023-03-11": 1}
    assert view["sampling"]["rows_read"] == 4 and view["sampling"]["rows_without_pickup_time"] == 1
    assert view["sampling"]["zero_or_negative_totals"] == 2 and view["sampling"]["pages"] == [
        "yellow_2023-03-07_p0.csv",
        "yellow_2023-03-11_p0.csv",
    ]
    assert (
        view["files"]["trips.csv"]["rows"] == 3
        and view["source_snapshot"] == f"nyc_tlc_yellow/{ev.TLC_SNAPSHOT}"
    )
    assert len(pd.read_csv(tmp_path / "o" / "nyc_tlc_yellow" / "trips.csv")) == 3


def _tlc_dir(root):
    raw = root / "nyc_tlc_yellow" / ev.TLC_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    return raw / "yellow_2023-03-07_p0.csv"


# --- openFDA device adverse event reports -----------------------------------------------------------------  # noqa: E501


def _maude(number, **extra):
    return {
        "report_number": number,
        "event_type": "Malfunction",
        "manufacturer_contact_f_name": "A",
        "manufacturer_contact_phone_number": "1",
        "mdr_text": [{"text": "free text", "mdr_text_key": "k"}],
        "device": [
            {
                "brand_name": "B",
                "manufacturer_contact_l_name": "nested",
                "openfda": {"device_class": "2"},
            }
        ],
        "patient": [{"patient_sex": "Unknown", "patient_problems": ["p"]}],
        **extra,
    }  # noqa: E501


def test_maude_view_drops_contact_persons_and_narratives_at_every_depth_and_orders_by_report_number():  # noqa: E501
    first = {"results": [_maude("B-2"), _maude("A-1", date_received="20230301")]}
    second = {"results": [_maude("B-2", event_type="Death"), _maude("C-3")]}
    view, repeated, dropped = ev.maude_view([first, second])
    assert [r["report_number"] for r in view] == ["A-1", "B-2", "C-3"] and repeated == 1
    assert view[1]["event_type"] == "Malfunction"  # the first of a repeated report is kept
    assert dropped == [
        "manufacturer_contact_f_name",
        "manufacturer_contact_l_name",
        "manufacturer_contact_phone_number",
        "mdr_text",
    ]
    for record in view:
        assert (
            not any(k.startswith("manufacturer_contact_") for k in record)
            and "mdr_text" not in record
        )
        assert (
            "manufacturer_contact_l_name" not in record["device"][0]
        )  # not even inside the device array
        assert record["device"][0]["openfda"] == {"device_class": "2"} and record["patient"][0][
            "patient_problems"
        ] == ["p"]
    assert ev.maude_view([{"results": []}]) == ([], 0, ["mdr_text"])


def _maude_snapshot(root, pages=2):
    raw = root / "openfda_device_event" / ev.MAUDE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    for k in range(pages):
        (raw / f"maude_20230301_s{k * 500:05d}.json").write_text(
            json.dumps({"results": [_maude(f"R-{k}-{i}") for i in range(2)]}), encoding="utf-8"
        )


def test_the_maude_builder_writes_sorted_json_lines_and_records_what_it_dropped(tmp_path):
    raw_root = tmp_path / "acquired"
    (raw_root / "openfda_device_event" / ev.MAUDE_SNAPSHOT / "raw").mkdir(parents=True)
    with pytest.raises(ev.ViewError, match="^no report page in the snapshot$"):
        ev._build_maude(raw_root, tmp_path / "o0", {})
    import shutil

    shutil.rmtree(raw_root)
    _maude_snapshot(raw_root)
    manifest: dict = {}
    ev._build_maude(raw_root, tmp_path / "o", manifest)
    lines = (tmp_path / "o" / "openfda_device_event" / "reports.jsonl").read_text().splitlines()
    assert [json.loads(line)["report_number"] for line in lines] == [
        "R-0-0",
        "R-0-1",
        "R-1-0",
        "R-1-1",
    ]
    assert lines[0].startswith('{"device"') and "free text" not in lines[0]
    view = manifest["openfda_device_event"]
    assert (
        view["sampling"]["reports"] == 4
        and view["sampling"]["repeated_reports"] == 0
        and view["sampling"]["pages"]
        == ["maude_20230301_s00000.json", "maude_20230301_s00500.json"]
    )
    assert view["sampling"]["dropped_keys"] == [
        "manufacturer_contact_f_name",
        "manufacturer_contact_l_name",
        "manufacturer_contact_phone_number",
        "mdr_text",
    ]
    assert (
        view["files"]["reports.jsonl"]["rows"] == 4
        and view["source_snapshot"] == f"openfda_device_event/{ev.MAUDE_SNAPSHOT}"
    )


def test_usda_spec_declares_keys_for_every_relation_and_uses_its_own_snapshot():
    spec = ev.TABLE_SETS["usda_fdc_sr_legacy"]
    assert spec["snapshot"] == "2026-11-22" and spec["archive"]["prefix"].endswith(
        "sr_legacy_food_csv_2018-04/"
    )
    for child, child_key, parent, parent_key in spec["relations"]:
        assert (
            child_key in spec["tables"][child]["keep"]
            and parent_key in spec["tables"][parent]["keep"]
        )
    assert set(spec["tables"]) == {
        "food",
        "food_category",
        "food_nutrient",
        "nutrient",
        "food_nutrient_derivation",
        "food_portion",
        "measure_unit",
    }


def test_taxi_view_keeps_the_file_order_of_trips_with_the_same_pickup_time_beyond_a_small_input():
    rows = [
        {"tpep_pickup_datetime": "2023-03-07T08:00:00.000", "total_amount": str(i)}
        for i in range(40)
    ]
    out = ev.taxi_trip_view([_tlc_page(rows[:25]), _tlc_page(rows[25:])])
    assert out["total_amount"].tolist() == [
        float(i) for i in range(40)
    ] and out.index.tolist() == list(range(40))


def test_the_tlc_builder_counts_a_total_of_exactly_one_dollar_or_less_as_zero_or_negative_only_up_to_zero(  # noqa: E501
    tmp_path,
):
    raw = tmp_path / "acquired" / "nyc_tlc_yellow" / ev.TLC_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    _tlc_page([{"total_amount": "0.5"}, {"total_amount": "1.0"}, {"total_amount": "0.0"}]).to_csv(
        raw / "yellow_2023-03-07_p0.csv", index=False
    )
    manifest: dict = {}
    ev._build_tlc(tmp_path / "acquired", tmp_path / "o", manifest)
    assert manifest["nyc_tlc_yellow"]["sampling"]["zero_or_negative_totals"] == 1


def test_stats19_spec_keeps_the_join_key_and_drops_police_references_and_home_areas():
    spec = ev.TABLE_SETS["dft_stats19_2023"]
    assert spec["snapshot"] == "2026-11-22" and set(spec["tables"]) == {
        "collision",
        "vehicle",
        "casualty",
    }
    for rule in spec["tables"].values():
        assert "collision_index" in rule["keep"] and "collision_ref_no" not in rule["keep"]
    assert "lsoa_of_driver" not in spec["tables"]["vehicle"]["keep"]
    assert "lsoa_of_casualty" not in spec["tables"]["casualty"]["keep"]
    assert [r[:2] + r[2:] for r in spec["relations"]] == [
        ["vehicle", "collision_index", "collision", "collision_index"],
        ["casualty", "collision_index", "collision", "collision_index"],
    ]


# --- EPA AQS hourly ozone and USGS continuous discharge --------------------------------------


def _aqs_rows(rows):
    base = {c: "1" for c in ev.AQS_COLUMNS}
    base.update(
        {
            "State Code": "01",
            "County Code": "003",
            "Site Num": "0010",
            "POC": "1",
            "Date GMT": "2022-03-01",
            "Time GMT": "07:00",
            "Sample Measurement": "0.040",
            "Units of Measure": ev.AQS_UNITS,
            "MDL": "0.005",
            "Qualifier": None,
            "Method Code": "087",
        }
    )
    return pd.DataFrame([{**base, **r} for r in rows], columns=list(ev.AQS_COLUMNS))


def test_aqs_pick_takes_an_even_stride_of_the_sorted_list_and_never_more_than_asked():
    ids = [f"m{n:02d}" for n in range(10)]
    assert ev.aqs_pick(list(reversed(ids)), 5) == ["m00", "m02", "m04", "m06", "m08"]
    assert ev.aqs_pick(ids, 3) == ["m00", "m03", "m06"]
    assert ev.aqs_pick(ids[:2], 5) == ["m00", "m01"]
    assert ev.aqs_pick(ids, 10) == ids


def test_aqs_view_is_in_utc_order_per_monitor_keeps_flags_and_counts_unreadable_times():
    chunk = _aqs_rows(
        [
            {"Time GMT": "09:00", "Qualifier": "IA"},
            {
                "Time GMT": "08:00",
                "Sample Measurement": "x",
                "MDL": "x",
                "Latitude": "99",
            },
            {"Site Num": "0020", "Time GMT": "07:00"},
            {"Date GMT": "03/01/2022", "Time GMT": "07:00"},
            {"Time GMT": "bad"},
            {"Site Num": "9999"},
        ]
    )
    view, places = ev.aqs_hourly_view(
        [chunk.iloc[:1], chunk.iloc[1:]], ["01-003-0010-1", "01-003-0020-1"]
    )
    assert list(view.columns) == [
        "monitor", "timestamp", "ozone_ppm", "mdl_ppm", "method_code", "qualifier"
    ]  # fmt: skip
    assert view["monitor"].tolist() == ["01-003-0010-1", "01-003-0010-1", "01-003-0020-1"]
    assert view["timestamp"].astype(str).tolist() == [
        "2022-03-01 08:00:00",
        "2022-03-01 09:00:00",
        "2022-03-01 07:00:00",
    ]
    assert view["qualifier"].tolist() == [pd.NA, "IA", pd.NA]
    assert view["ozone_ppm"].isna().tolist() == [True, False, False]
    assert pd.isna(view["mdl_ppm"].iloc[0]) and view["mdl_ppm"].tolist()[1:] == [0.005, 0.005]
    assert view["method_code"].tolist() == ["087"] * 3
    assert view.attrs["rows_dropped"] == 2
    assert places["monitor"].tolist() == ["01-003-0010-1", "01-003-0020-1"]
    assert list(places.columns) == ["monitor", "latitude", "longitude"]


def test_aqs_view_refuses_another_unit():
    with pytest.raises(ev.ViewError) as exc_info:
        ev.aqs_hourly_view(
            [_aqs_rows([{"Units of Measure": "Parts per billion"}])], ["01-003-0010-1"]
        )
    assert str(exc_info.value) == "unexpected unit of measure"


def test_aqs_chunks_passes_exact_columns_and_chunksize(tmp_path, monkeypatch):
    import zipfile

    zpath = tmp_path / "aqs.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("aqs.csv", _aqs_rows([{}]).to_csv(index=False))
    seen = {}
    real_read_csv = pd.read_csv

    def spy(handle, *args, **kwargs):
        seen.update(kwargs)
        return real_read_csv(handle, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", spy)
    chunks = list(ev._aqs_chunks(zpath, ev.AQS_COLUMNS[:4]))
    assert len(chunks) == 1
    assert seen["usecols"] == list(ev.AQS_COLUMNS[:4])
    assert seen["chunksize"] == 500_000


def _aqs_snapshot(root):
    import zipfile

    raw = root / "epa_aqs_ozone_hourly" / ev.AQS_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    for year in ev.AQS_YEARS:
        frame = _aqs_rows(
            [
                {"Date GMT": f"{year}-03-01"},
                {"Date GMT": f"{year}-03-01", "Site Num": "0020"},
                {"Date GMT": f"{year}-03-01", "Site Num": "0030"},
            ]
        )
        if year == ev.AQS_YEARS[0]:
            extra = frame.iloc[[0]].copy()
            extra["Site Num"] = "0099"
            frame = pd.concat([frame, extra], ignore_index=True)
        with zipfile.ZipFile(raw / f"hourly_44201_{year}.zip", "w") as z:
            z.writestr(f"hourly_44201_{year}.csv", frame.to_csv(index=False))


def test_aqs_builder_selects_monitors_present_in_both_years_and_records_the_sampling(
    tmp_path, monkeypatch
):
    root = tmp_path / "acq"
    _aqs_snapshot(root)
    monkeypatch.setattr(ev, "AQS_MONITORS", 2)
    manifest = {}
    ev._build_aqs(root, tmp_path / "out", manifest)
    view = manifest["epa_aqs_ozone_hourly"]
    assert view["files"]["ozone.csv"]["rows"] == 4 and view["files"]["monitors.csv"]["rows"] == 2
    sampling = view["sampling"]
    assert sampling["monitors_in_both_years"] == 3 and sampling["monitors"] == 2
    assert sampling["hours_by_monitor"] == {"01-003-0010-1": 2, "01-003-0020-1": 2}
    assert sampling["years"] == [2022, 2023] and sampling["rows_dropped"] == 0
    assert sampling["missing_value_share"] == 0.0 and sampling["flagged_share"] == 0.0
    assert view["source_snapshot"] == f"epa_aqs_ozone_hourly/{ev.AQS_SNAPSHOT}"


def test_aqs_builder_rounds_shares_and_uses_first_four_columns_for_ids(tmp_path, monkeypatch):
    import zipfile

    root = tmp_path / "acq"
    raw = root / "epa_aqs_ozone_hourly" / ev.AQS_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    for year in ev.AQS_YEARS:
        rows = [
            {"Date GMT": f"{year}-03-01", "Sample Measurement": "bad", "Qualifier": "IA"},
            {"Date GMT": f"{year}-03-01", "Time GMT": "08:00"},
            {"Date GMT": f"{year}-03-01", "Time GMT": "09:00"},
        ]
        with zipfile.ZipFile(raw / f"hourly_44201_{year}.zip", "w") as z:
            z.writestr(f"hourly_44201_{year}.csv", _aqs_rows(rows).to_csv(index=False))
    monkeypatch.setattr(ev, "AQS_MONITORS", 1)
    manifest: dict = {}
    ev._build_aqs(root, tmp_path / "out", manifest)
    assert manifest["epa_aqs_ozone_hourly"]["sampling"]["missing_value_share"] == 0.3333
    assert manifest["epa_aqs_ozone_hourly"]["sampling"]["flagged_share"] == 0.3333


def _usgs_page(rows):
    features = [
        {
            "properties": {
                "monitoring_location_id": "USGS-1",
                "time": "2022-01-01T00:00:00+00:00",
                "value": "10",
                "unit_of_measure": "ft^3/s",
                "approval_status": "Approved",
                "qualifier": None,
                **row,
            }
        }
        for row in rows
    ]
    return {"features": features}


def test_usgs_view_is_in_utc_order_deduplicates_and_keeps_status_and_qualifier():
    page_a = _usgs_page(
        [
            {"time": "2022-01-01T00:30:00+00:00", "value": "x", "approval_status": "Provisional"},
            {"time": "2022-01-01T00:15:00+00:00", "qualifier": "ICE"},
            {"monitoring_location_id": "USGS-0", "time": "2022-01-01T05:00:00+01:00"},
        ]
    )
    page_b = _usgs_page([{"time": "2022-01-01T00:15:00+00:00", "value": "99"}, {"time": "bad"}])
    view = ev.usgs_continuous_view([page_a, page_b])
    assert list(view.columns) == [
        "monitor",
        "timestamp",
        "discharge_cfs",
        "approval_status",
        "qualifier",
    ]
    assert view["monitor"].tolist() == ["USGS-0", "USGS-1", "USGS-1"]
    assert view["timestamp"].astype(str).tolist() == [
        "2022-01-01 04:00:00",
        "2022-01-01 00:15:00",
        "2022-01-01 00:30:00",
    ]
    assert view["discharge_cfs"].isna().tolist() == [False, False, True]
    assert view["discharge_cfs"].tolist()[:2] == [10.0, 10.0]
    assert view["qualifier"].isna().tolist() == [True, False, True]
    assert view["qualifier"].iloc[1] == "ICE"
    assert view["approval_status"].tolist() == ["Approved", "Approved", "Provisional"]
    assert view.attrs["duplicates"] == 1


def test_usgs_view_refuses_another_unit_and_handles_empty_pages():
    with pytest.raises(ev.ViewError) as exc_info:
        ev.usgs_continuous_view([_usgs_page([{"unit_of_measure": "m^3/s"}])])
    assert str(exc_info.value) == "unexpected unit of measure"
    empty = ev.usgs_continuous_view([{"features": []}])
    assert list(empty.columns) == [
        "monitor",
        "timestamp",
        "discharge_cfs",
        "approval_status",
        "qualifier",
    ]
    assert len(empty) == 0


def _usgs_snapshot(root):
    raw = root / "usgs_continuous_discharge" / ev.USGS_SNAPSHOT / "raw"
    _w(
        raw / "discharge_1_p0.json",
        json.dumps(_usgs_page([{}, {"time": "2022-01-01T00:15:00+00:00"}])),
    )
    _w(raw / "discharge_1_p1.json", json.dumps(_usgs_page([{"time": "2022-01-01T00:30:00+00:00"}])))


def test_usgs_builder_reads_every_page_and_records_cadence_and_status(tmp_path):
    root = tmp_path / "acq"
    _usgs_snapshot(root)
    manifest = {}
    ev._build_usgs(root, tmp_path / "out", manifest)
    view = manifest["usgs_continuous_discharge"]
    assert view["files"]["discharge.csv"]["rows"] == 3
    sampling = view["sampling"]
    assert sampling["pages"] == ["discharge_1_p0.json", "discharge_1_p1.json"]
    assert sampling["median_step_minutes"] == {"USGS-1": 15.0}
    assert sampling["provisional_share"] == 0.0 and sampling["duplicates"] == 0
    assert sampling["first_by_monitor"] == {"USGS-1": "2022-01-01 00:00:00"}
    with pytest.raises(ev.ViewError) as exc_info:
        ev._build_usgs(tmp_path / "none", tmp_path / "out", {})
    assert str(exc_info.value) == "no discharge page in the snapshot"


def test_usgs_builder_rounds_missing_and_provisional_shares(tmp_path):
    raw = tmp_path / "acq" / "usgs_continuous_discharge" / ev.USGS_SNAPSHOT / "raw"
    _w(
        raw / "discharge_1_p0.json",
        json.dumps(
            _usgs_page(
                [
                    {},
                    {
                        "time": "2022-01-01T00:15:00+00:00",
                        "value": "bad",
                        "approval_status": "Provisional",
                    },
                    {"time": "2022-01-01T00:30:00+00:00"},
                ]
            )
        ),
    )
    manifest: dict = {}
    ev._build_usgs(tmp_path / "acq", tmp_path / "out", manifest)
    sampling = manifest["usgs_continuous_discharge"]["sampling"]
    assert sampling["missing_value_share"] == 0.3333 and sampling["provisional_share"] == 0.3333


# --- Wikimedia stub history ---------------------------------------------------------------------


def _wiki_revision(rid, parent=None, who="<username>Ann</username><id>7</id>", extra="", ts=None):
    return (
        f"    <revision><id>{rid}</id>"
        + (f"<parentid>{parent}</parentid>" if parent else "")
        + f"<timestamp>{ts or '2003-03-27T09:24:48Z'}</timestamp>"
        + f"<contributor>{who}</contributor>{extra}"
        + '<text bytes="724" sha1="x" /></revision>'
    )


def _wiki_lines(*pages):
    lines = ['<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">', "  <siteinfo />"]
    for pid, ns, revisions, closed in pages:
        lines += [
            "  <page>",
            "    <title>Secret</title>",
            f"    <ns>{ns}</ns>",
            f"    <id>{pid}</id>",
        ]
        lines += revisions + (["  </page>"] if closed else [])
    return lines


def test_wiki_view_hashes_contributors_drops_names_and_keeps_revision_facts():
    revisions = [
        _wiki_revision(10, extra="<comment>edit summary</comment>", ts="2003-03-27T11:24:48+02:00"),
        _wiki_revision(
            11, parent=10, who="<ip>10.0.0.1</ip>", extra="<minor />", ts="2003-04-01T00:00:00Z"
        ),
        _wiki_revision(12, parent=11, who='<username deleted="deleted" />', ts="bad"),
        "    <revision><id>13</id><parentid>bad</parentid><timestamp>2003-04-02T00:00:00Z</timestamp></revision>",  # noqa: E501
    ]
    view = ev.wiki_revision_view(
        _wiki_lines((1, 0, revisions, True), (2, 4, [_wiki_revision(20)], True))
    )
    assert list(view.columns) == list(ev.WIKI_COLUMNS)
    assert view["page_id"].tolist() == [1, 1, 1, 1, 2]
    assert view["namespace"].tolist() == [0, 0, 0, 0, 4]
    assert view["revision_id"].tolist() == [10, 11, 12, 13, 20]
    assert view["parent_id"].isna().tolist() == [True, False, False, True, True]
    assert view["timestamp"].astype(str).tolist()[:2] == [
        "2003-03-27 09:24:48",
        "2003-04-01 00:00:00",
    ]
    assert pd.isna(view["timestamp"].iloc[2])
    assert view["editor_kind"].tolist() == [
        "registered",
        "anonymous",
        "unknown",
        "unknown",
        "registered",
    ]
    assert view["editor"].tolist()[0] == ev.pseudonym("user:7") == view["editor"].tolist()[4]
    assert view["editor"].tolist()[1] == ev.pseudonym("ip:10.0.0.1") and pd.isna(
        view["editor"].tolist()[2]
    )
    assert view["minor"].tolist() == [False, True, False, False, False]
    assert view["has_comment"].tolist() == [True, False, False, False, False]
    assert view["text_bytes"].tolist()[:3] == [724, 724, 724]
    assert pd.isna(view["text_bytes"].iloc[3])
    assert str(view["parent_id"].dtype) == "Int64"
    assert (
        "Ann" not in view.to_csv()
        and "10.0.0.1" not in view.to_csv()
        and "Secret" not in view.to_csv()
    )
    assert view.attrs["incomplete_pages"] == 0
    empty_view = ev.wiki_revision_view(_wiki_lines((1, 0, [], True)))
    assert list(empty_view.columns) == list(ev.WIKI_COLUMNS) and len(empty_view) == 0


def test_wiki_view_drops_the_unclosed_last_page_and_counts_it():
    lines = _wiki_lines(
        (1, 0, [_wiki_revision(10)], True),
        (2, 0, [_wiki_revision(20)], True),
        (3, 0, [_wiki_revision(30)], False),
    )
    view = ev.wiki_revision_view(lines)
    assert view["page_id"].tolist() == [1, 2] and view.attrs["incomplete_pages"] == 1
    no_tail = ev.wiki_revision_view(["<mediawiki>", "  <page>", "  </page>"])
    assert no_tail.attrs["incomplete_pages"] == 0 and len(no_tail) == 0


def test_wiki_view_refuses_a_stream_without_a_closed_page_and_a_doctype():
    with pytest.raises(ev.ViewError) as exc_empty:
        ev.wiki_revision_view(_wiki_lines((1, 0, [_wiki_revision(10)], False)))
    assert str(exc_empty.value) == "no complete page in the stub history"
    lines = _wiki_lines((1, 0, [_wiki_revision(10)], True))
    for decl in ("<!DOCTYPE x>", "<!ENTITY a 'b'>"):
        with pytest.raises(ev.ViewError) as exc_decl:
            ev.wiki_revision_view([decl, *lines])
        assert str(exc_decl.value) == "document type declarations are refused"


def test_gzip_members_lines_reads_every_member_and_drops_a_torn_line():
    import gzip

    assert ev.gzip_members_lines(b"") == ([], True)
    blob = gzip.compress(b"a 1\nb 2\n") + gzip.compress(b"c\nd")
    assert ev.gzip_members_lines(blob) == (["a 1", "b 2", "c", "d"], True)
    import zlib

    packer = zlib.compressobj(wbits=31)
    second = packer.compress(b"c\nd1\nd2") + packer.flush(zlib.Z_FULL_FLUSH)
    lines, complete = ev.gzip_members_lines(gzip.compress(b"a\nb\n") + second)
    assert lines == ["a", "b", "c", "d1"] and complete is False
    with pytest.raises(zlib.error):
        ev.gzip_members_lines(zlib.compress(b"plain zlib"))


def _wiki_snapshot(root):
    import gzip

    raw = root / "wikimedia_simplewiki_edits" / ev.WIKI_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    lines = _wiki_lines((1, 0, [_wiki_revision(10), _wiki_revision(11, parent=10)], True))
    text = "\n".join(lines) + "\n"
    head, tail = text.split("  <page>", 1)
    (raw / "stub_meta_history_head.xml.gz").write_bytes(
        gzip.compress(head.encode()) + gzip.compress(("  <page>" + tail).encode())
    )


def test_wiki_builder_reads_a_multi_member_stream_and_records_the_sampling(tmp_path):
    root = tmp_path / "acq"
    _wiki_snapshot(root)
    manifest = {}
    ev._build_wiki(root, tmp_path / "out", manifest)
    view = manifest["wikimedia_simplewiki_edits"]
    assert view["files"]["revisions.csv"]["rows"] == 2 and view["pseudonymised"] == ["editor"]
    sampling = view["sampling"]
    assert sampling["pages"] == 1 and sampling["stream_complete"] is True
    assert sampling["parents_outside_view"] == 0 and sampling["incomplete_pages"] == 0
    assert (
        sampling["first_revision"] == "2003-03-27 09:24:48" and sampling["anonymous_share"] == 0.0
    )
    assert view["salt_label"] == ev.SALT


def test_wiki_builder_rounds_anonymous_share(tmp_path):
    import gzip

    raw = tmp_path / "acq" / "wikimedia_simplewiki_edits" / ev.WIKI_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    lines = _wiki_lines(
        (
            1,
            0,
            [_wiki_revision(10), _wiki_revision(11, who="<ip>10.0.0.2</ip>"), _wiki_revision(12)],
            True,
        )
    )
    (raw / "stub_meta_history_head.xml.gz").write_bytes(
        gzip.compress(("\n".join(lines) + "\n").encode())
    )
    manifest: dict = {}
    ev._build_wiki(tmp_path / "acq", tmp_path / "out", manifest)
    assert manifest["wikimedia_simplewiki_edits"]["sampling"]["anonymous_share"] == 0.3333


def _uniprot_snapshot(root):
    raw = root / "uniprot_kb_reviewed" / ev.UNIPROT_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    p1 = {
        "results": [
            {
                "primaryAccession": "P20000",
                "comments": [{"texts": [{"value": "Mail user@example.org"}]}],
                "references": [{"citation": {"authors": ["Doe J."]}}],
                "sequence": {"value": "MKT", "length": 3},
            },
            {
                "primaryAccession": "P10000",
                "entryType": "UniProtKB reviewed (Swiss-Prot)",
                "references": [{"citation": {"authors": ["First"]}}],
            },
        ]
    }
    p2 = {
        "results": [
            {
                "primaryAccession": "P10000",
                "entryType": "DUPLICATE_SHOULD_NOT_WIN",
            }
        ]
    }
    (raw / "uniprot_mouse_10090.json").write_text(json.dumps(p2))
    (raw / "uniprot_human_9606.json").write_text(json.dumps(p1))
    (raw / "manifest.json").write_text("{}")


def _osv_snapshot(root):
    import zipfile as _z

    raw = root / "osv_go_advisories" / ev.OSV_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with _z.ZipFile(raw / "osv_go_all.zip", "w") as z:
        z.writestr(
            "GO-2024-0002.json",
            json.dumps(
                {
                    "summary": "bug",
                    "id": "GO-2024-0002",
                    "credits": [{"name": "Alice"}],
                    "details": "Report to sec@example.org",
                }
            ),
        )
        z.writestr(
            "GO-2024-0001.json",
            json.dumps({"id": "GO-2024-0001", "summary": "first"}),
        )
        z.writestr(
            "sub/GO-2024-0001.json",
            json.dumps({"id": "GO-2024-0001", "summary": "dup"}),
        )
        z.writestr(
            "GHSA-1111-2222-3333.json",
            json.dumps({"id": "GHSA-1111-2222-3333", "summary": "non-go"}),
        )
        z.writestr("README.txt", "ignored")


def test_uniprot_view_drops_citations_sequence_redacts_emails_and_keeps_first_accession():
    raw_entries = [
        {
            "sequence": {"value": "MK"},
            "primaryAccession": "P2",
            "references": [{"citation": "c"}],
            "comments": [{"note": "ask ops@example.org"}],
        },
        {"primaryAccession": "P1", "annotationScore": 5.0},
        {"primaryAccession": "P1", "annotationScore": 1.0},
    ]
    raw_copy = json.loads(json.dumps(raw_entries))
    out = ev.uniprot_view(raw_entries)
    assert raw_entries == raw_copy
    assert [r["primaryAccession"] for r in out] == ["P1", "P2"]
    assert out[0]["annotationScore"] == 5.0
    assert "references" not in out[1] and "sequence" not in out[1]
    assert out[1]["comments"][0]["note"] == "ask [email]"


def test_uniprot_builder_writes_sorted_jsonl_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match="no UniProt file"):
        ev._build_uniprot(tmp_path / "empty", tmp_path / "out_err", {})
    root = tmp_path / "acq"
    _uniprot_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_uniprot(root, out, manifest)
    ev._build_uniprot(root, out, manifest)
    target = out / "uniprot_kb_reviewed" / "entries.jsonl"
    lines = target.read_text().splitlines()
    assert len(lines) == 2 and target.read_text().endswith("\n")
    assert lines[0] == json.dumps(
        {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P10000"},
        sort_keys=True,
    )
    assert lines[1] == json.dumps(
        {"comments": [{"texts": [{"value": "Mail [email]"}]}], "primaryAccession": "P20000"},
        sort_keys=True,
    )
    view = manifest["uniprot_kb_reviewed"]
    assert view["dropped"] == ["references", "sequence"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"uniprot_kb_reviewed/{ev.UNIPROT_SNAPSHOT}"
    assert view["files"]["entries.jsonl"]["rows"] == 2
    assert view["sampling"] == {
        "entries_in": 3,
        "files": ["uniprot_human_9606.json", "uniprot_mouse_10090.json"],
        "method": "250 reviewed Swiss-Prot entries per organism across six model organisms",
    }


def test_osv_go_view_filters_non_go_prefixes_drops_credits_and_redacts_emails():
    raw_records = [
        {"id": "GHSA-xxxx", "summary": "skip"},
        {
            "summary": "two",
            "id": "GO-2023-0002",
            "credits": [{"name": "Bob"}],
            "details": "b@ex.org",
        },
        {"id": "GO-2023-0001", "summary": "first"},
        {"id": "GO-2023-0001", "summary": "second"},
    ]
    out = ev.osv_go_view(raw_records)
    assert [r["id"] for r in out] == ["GO-2023-0001", "GO-2023-0002"]
    assert out[0]["summary"] == "first"
    assert "credits" not in out[1] and out[1]["details"] == "[email]"


def test_osv_go_builder_writes_sorted_jsonl_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match="no OSV Go zip"):
        ev._build_osv_go(tmp_path / "empty", tmp_path / "out_err", {})
    root = tmp_path / "acq"
    _osv_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_osv_go(root, out, manifest)
    ev._build_osv_go(root, out, manifest)
    target = out / "osv_go_advisories" / "advisories.jsonl"
    lines = target.read_text().splitlines()
    assert len(lines) == 2 and target.read_text().endswith("\n")
    assert lines[0] == json.dumps({"id": "GO-2024-0001", "summary": "first"}, sort_keys=True)
    assert lines[1] == json.dumps(
        {"details": "Report to [email]", "id": "GO-2024-0002", "summary": "bug"},
        sort_keys=True,
    )
    view = manifest["osv_go_advisories"]
    assert view["dropped"] == ["credits"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"osv_go_advisories/{ev.OSV_SNAPSHOT}"
    assert view["files"]["advisories.jsonl"]["rows"] == 2
    assert view["sampling"] == {
        "archive_records": 4,
        "go_records": 2,
        "method": "all GO-* Go Vulnerability Database advisories from Go/all.zip (non-GO prefixes excluded to stay under CC BY 4.0)",  # noqa: E501
    }


def _gfz_snapshot(root):
    raw = root / "gfz_kp_index" / ev.GFZ_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    lines = [
        "# LICENSE: CC BY 4.0",
        "",
        "2020 01 02 03.0 04.50 1 2 2.333 9 1",
        "2020 01 01 00.0 01.50 1 2 -1.000 -1 0",
        "2020 99 01 00.0 01.50 1 2 1.000 4 0",
    ]
    (raw / "Kp_ap_since_1932.txt").write_text("\n".join(lines) + "\n")


def _dwd_snapshot(root):
    import zipfile as _z

    raw = root / "dwd_hourly_climate" / ev.DWD_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with _z.ZipFile(raw / "stundenwerte_TU_00044_20070401_20251231_hist.zip", "w") as z:
        z.writestr("Metadaten_Geographie.txt", "ignored\n")
        z.writestr(
            "produkt_tu_stunde_20070401_20251231_00044.txt",
            (
                "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n"
                "   44;2017123123;3;5.0;80.0;eor\n"
                "   44;2018010101;3;-999;-999;eor\n"
                "   44;2018010100;3;4.2;85.0;eor\n"
                "   44;2018010100;3;9.9;99.0;eor\n"
                "   44;2018990100;3;1.0;50.0;eor\n"
            ),
        )
        z.writestr("produkt_tu_stunde_readme.info", "ignored\n")
    (raw / "ignore.zip").write_bytes(b"")


def _rte_snapshot(root):
    raw = root / "rte_eco2mix_national" / ev.RTE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    csv_text = (
        "perimetre;nature;date;heure;date_heure;consommation;nucleaire\n"
        "France;Donnees definitives;2020-03-29;03:00;2020-03-29T01:00:00+00:00;47000;30500\n"
        "France;Donnees definitives;2020-03-29;02:00;2020-03-29T01:00:00+00:00;46000;30000\n"
        "France;Donnees definitives;2020-01-01;00:15;2019-12-31T23:15:00+00:00;;\n"
        "France;Donnees definitives;2020-01-01;00:00;2019-12-31T23:00:00+00:00;63000;49000\n"
        "France;Donnees definitives;bad;00:00;not-a-date;50000;40000\n"
    )
    (raw / "eco2mix_national_2020.csv").write_bytes(csv_text.encode("utf-8-sig"))
    (raw / "other.csv").write_text("x\n")


def test_gfz_kp_view_parses_timestamps_sorts_and_maps_sentinels():
    lines = [
        "# header",
        "   ",
        "2020 01 02 03.0 04.50 1 2 2.333 9 1",
        "2020 01 01 00.0 01.50 1 2 -1.000 -1 0",
        "2020 01 03 06.0 07.50 1 2 bad bad bad",
        "2020 13 01 00.0 01.50 1 2 1.000 5 1",
    ]
    out = ev.gfz_kp_view(lines)
    assert out.columns.tolist() == ["timestamp", "kp", "ap", "definitive"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2020-01-01 00:00:00"),
        pd.Timestamp("2020-01-02 03:00:00"),
        pd.Timestamp("2020-01-03 06:00:00"),
    ]
    assert pd.isna(out["kp"].iloc[0]) and pd.isna(out["ap"].iloc[0])
    assert out["kp"].iloc[1] == 2.333 and out["ap"].iloc[1] == 9.0
    assert pd.isna(out["kp"].iloc[2]) and pd.isna(out["ap"].iloc[2])
    assert pd.isna(out["definitive"].iloc[2])
    assert out["definitive"].iloc[:2].tolist() == [0, 1]
    assert str(out["definitive"].dtype) == "Int64"


def test_gfz_kp_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no GFZ Kp file in the snapshot$"):
        ev._build_gfz_kp(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _gfz_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_gfz_kp(root, out, manifest)
    ev._build_gfz_kp(root, out, manifest)
    target = out / "gfz_kp_index" / "kp_ap.csv"
    assert target.read_text().splitlines()[0] == "timestamp,kp,ap,definitive"
    view = manifest["gfz_kp_index"]
    assert view["files"]["kp_ap.csv"]["rows"] == 2
    assert view["dropped"] == ["half_hour_midpoint", "days_since_1932", "midpoint_days"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"gfz_kp_index/{ev.GFZ_SNAPSHOT}"
    assert view["sampling"] == {
        "definitive_rows": 1,
        "first_timestamp": "2020-01-01 00:00:00",
        "last_timestamp": "2020-01-02 03:00:00",
        "method": "complete GFZ Niemegk 3-hourly Kp/ap time series",
        "missing_kp_rows": 1,
    }


def test_dwd_hourly_view_filters_start_dedupes_sorts_and_maps_missing():
    f1 = pd.DataFrame(
        {
            "STATIONS_ID": ["  44", "  44", "  44", "  44", " 10"],
            "MESS_DATUM": [2017123123, 2018010101, 2018010100, 2018010100, 2018990100],
            "QN_9": [3, 3, 3, 9, 1],
            "TT_TU": [5.0, -999.0, 4.2, 8.8, 1.0],
            "RF_TU": [80.0, -999.0, 85.0, 99.0, 50.0],
        }
    )
    f2 = pd.DataFrame(
        {
            "STATIONS_ID": ["  10"],
            "MESS_DATUM": [2018010200],
            "QN_9": ["bad"],
            "TT_TU": ["bad"],
            "RF_TU": ["bad"],
        }
    )
    out = ev.dwd_hourly_view([f1, f2])
    assert out.columns.tolist() == [
        "station_id",
        "timestamp",
        "temp_c",
        "rel_humidity_pct",
        "quality_code",
    ]
    assert out["station_id"].tolist() == ["10", "44", "44"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2018-01-02 00:00:00"),
        pd.Timestamp("2018-01-01 00:00:00"),
        pd.Timestamp("2018-01-01 01:00:00"),
    ]
    assert out["temp_c"].iloc[1] == 4.2 and pd.isna(out["temp_c"].iloc[0])
    assert pd.isna(out["temp_c"].iloc[2]) and pd.isna(out["rel_humidity_pct"].iloc[0])
    assert out["rel_humidity_pct"].iloc[1] == 85.0 and pd.isna(out["rel_humidity_pct"].iloc[2])
    assert pd.isna(out["quality_code"].iloc[0]) and out["quality_code"].iloc[1:].tolist() == [3, 3]
    assert str(out["quality_code"].dtype) == "Int64"
    assert out.attrs == {"duplicates": 1}


def test_dwd_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no DWD station archive in the snapshot$"):
        ev._build_dwd(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _dwd_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_dwd(root, out, manifest)
    ev._build_dwd(root, out, manifest)
    target = out / "dwd_hourly_climate" / "air_temperature.csv"
    assert (
        target.read_text().splitlines()[0]
        == "station_id,timestamp,temp_c,rel_humidity_pct,quality_code"
    )  # noqa: E501
    view = manifest["dwd_hourly_climate"]
    assert view["files"]["air_temperature.csv"]["rows"] == 2
    assert view["dropped"] == ["eor_marker"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"dwd_hourly_climate/{ev.DWD_SNAPSHOT}"
    assert view["sampling"] == {
        "archives": 1,
        "duplicates_dropped": 1,
        "first_timestamp": "2018-01-01 00:00:00",
        "last_timestamp": "2018-01-01 01:00:00",
        "method": "12 strided DWD hourly TU stations filtered from 2018-01-01 onward",
        "stations": 1,
    }


def test_rte_eco2mix_view_filters_half_hourly_dedupes_dst_and_sorts():
    df = pd.DataFrame(
        {
            "perimetre": ["France"] * 6,
            "nature": ["Def"] * 6,
            "date": ["d"] * 6,
            "heure": ["h"] * 6,
            "date_heure": [
                "2020-03-29T01:00:00+00:00",
                "2020-03-29T01:00:00+00:00",
                "2020-01-01T00:15:00+00:00",
                "2020-01-01T00:00:00+00:00",
                "2020-06-01T02:00:00+02:00",
                "bad",
            ],
            "consommation": [47000, 46000, None, 63000, 41000, 50000],
            "nucleaire": [30500, 30000, None, 49000, "bad", 40000],
        }
    )
    out = ev.rte_eco2mix_view([df])
    assert out.columns.tolist() == ["timestamp", "consommation", "nucleaire"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2020-01-01 00:00:00"),
        pd.Timestamp("2020-03-29 01:00:00"),
        pd.Timestamp("2020-06-01 00:00:00"),
    ]
    assert out["consommation"].tolist() == [63000.0, 47000.0, 41000.0]
    assert pd.isna(out["nucleaire"].iloc[2])
    assert out.attrs == {
        "duplicates": 1,
        "quarter_hour_rows_dropped": 1,
        "unreadable_timestamps": 1,
    }


def test_rte_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no RTE eco2mix file in the snapshot$"):
        ev._build_rte(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _rte_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_rte(root, out, manifest)
    ev._build_rte(root, out, manifest)
    target = out / "rte_eco2mix_national" / "eco2mix.csv"
    assert target.read_text().splitlines()[0] == "timestamp,consommation,nucleaire"
    view = manifest["rte_eco2mix_national"]
    assert view["files"]["eco2mix.csv"]["rows"] == 2
    assert view["dropped"] == ["perimetre", "nature", "date", "heure"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"rte_eco2mix_national/{ev.RTE_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "files": ["eco2mix_national_2020.csv"],
        "first_timestamp": "2019-12-31 23:00:00",
        "last_timestamp": "2020-03-29 01:00:00",
        "method": "half-hourly definitive RTE eco2mix national grid series for 2020-2023",
        "quarter_hour_rows_dropped": 1,
        "unreadable_timestamps": 1,
    }


def _ademe_row(dpe_id="d1", date="2024-03-15", ges="25.5"):
    return {
        "numero_dpe": dpe_id,
        "date_etablissement_dpe": date,
        "etiquette_dpe": "C",
        "annee_construction": "1995",
        "surface_habitable_logement": "72.0",
        "conso_5_usages_par_m2_ep": "140",
        "emission_ges_5_usages par_m2": ges,
        "qualite_isolation_plancher bas": "bonne",
    }


def _ademe_snapshot(root):
    raw = root / "ademe_dpe_existant" / ev.ADEME_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([_ademe_row("d2", "2024-06-14", "bad")]).to_csv(
        raw / "dpe_2024_06_14.csv", index=False
    )
    pd.DataFrame([_ademe_row("d1", "2024-03-15", "20.5"), _ademe_row("d1", "2024-09-01")]).to_csv(
        raw / "dpe_2024_03_15.csv", index=False
    )
    (raw / "other.csv").write_text("ignored\n")


def _alim_row(ins_id="i1", date="2024-05-01"):
    row = {col: f"v_{col}" for col in ev.ALIM_KEEP}
    row["numero_inspection"] = ins_id
    row["date_inspection"] = date
    row["enseigne"] = "Secret Cafe"
    row["siret"] = "12345678900012"
    return row


def _alim_snapshot(root):
    raw = root / "dgal_alimconfiance" / ev.ALIM_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame(
        [
            _alim_row("i2", "2024-06-01"),
            _alim_row("i1", "2024-04-01"),
            _alim_row("i1", "2024-09-01"),
        ]
    ).to_csv(raw / "export_alimconfiance.csv", sep=";", index=False)


def test_ademe_dpe_view_normalises_spaces_pseudonymises_dedupes_and_coerces():
    f1 = pd.DataFrame([_ademe_row("d2", "2024-06-14", "bad")])
    f2 = pd.DataFrame([_ademe_row("d1", "2024-03-15", "18.5"), _ademe_row("d1", "2024-09-01")])
    out = ev.ademe_dpe_view([f1, f2])
    assert "emission_ges_5_usages_par_m2" in out and "qualite_isolation_plancher_bas" in out
    assert "emission_ges_5_usages par_m2" not in out
    assert out["numero_dpe"].tolist() == [ev.pseudonym("d1"), ev.pseudonym("d2")]
    assert out["date_etablissement_dpe"].tolist() == ["2024-03-15", "2024-06-14"]
    assert out["emission_ges_5_usages_par_m2"].iloc[0] == 18.5
    assert pd.isna(out["emission_ges_5_usages_par_m2"].iloc[1])
    assert out["surface_habitable_logement"].iloc[0] == 72.0
    assert out.attrs == {"duplicates": 1}


def test_ademe_dpe_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no ADEME DPE file in the snapshot$"):
        ev._build_ademe_dpe(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _ademe_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_ademe_dpe(root, out, manifest)
    ev._build_ademe_dpe(root, out, manifest)
    target = out / "ademe_dpe_existant" / "dpe.csv"
    header = target.read_text().splitlines()[0]
    assert "emission_ges_5_usages_par_m2" in header and "qualite_isolation_plancher_bas" in header
    view = manifest["ademe_dpe_existant"]
    assert view["files"]["dpe.csv"]["rows"] == 2 and view["pseudonymised"] == ["numero_dpe"]
    assert view["salt_label"] == ev.SALT
    assert view["dropped"] == ["addresses", "ban_identifiers", "rnb_identifiers", "coordinates"]
    assert view["source_snapshot"] == f"ademe_dpe_existant/{ev.ADEME_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "files": ["dpe_2024_03_15.csv", "dpe_2024_06_14.csv"],
        "method": "five fixed 2024 dates (10,000 rows per date) with coded attributes only",
    }


def test_alimconfiance_view_projects_columns_pseudonymises_dedupes_and_sorts():
    df = pd.DataFrame(
        [
            _alim_row("i2", "2024-06-01"),
            _alim_row("i1", "2024-04-01"),
            _alim_row("i1", "2024-09-01"),
        ]
    )
    out = ev.alimconfiance_view(df)
    assert out.columns.tolist() == list(ev.ALIM_KEEP)
    assert "enseigne" not in out and "siret" not in out
    assert out["date_inspection"].tolist() == ["2024-04-01", "2024-06-01"]
    assert out["numero_inspection"].tolist() == [ev.pseudonym("i1"), ev.pseudonym("i2")]
    assert out.attrs == {"duplicates": 1}


def test_alimconfiance_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no DGAL AlimConfiance file in the snapshot$"):
        ev._build_alimconfiance(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _alim_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_alimconfiance(root, out, manifest)
    ev._build_alimconfiance(root, out, manifest)
    target = out / "dgal_alimconfiance" / "inspections.csv"
    assert target.read_text().splitlines()[0] == ",".join(ev.ALIM_KEEP)
    view = manifest["dgal_alimconfiance"]
    assert view["files"]["inspections.csv"]["rows"] == 2
    assert view["pseudonymised"] == ["numero_inspection"]
    assert view["salt_label"] == ev.SALT
    assert view["dropped"] == [
        "establishment_names",
        "siret",
        "agrement",
        "addresses",
        "communes",
        "geo",
    ]
    assert view["source_snapshot"] == f"dgal_alimconfiance/{ev.ALIM_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "method": "complete Alim'Confiance register projected to coded non-identifying attributes",
    }


def _ev_snapshot(root):
    raw = root / "zen_ev_charging" / ev.EV_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    text = (
        '"location";"user_id";"session_id";"plugin_time";"plugout_time";"connection_time";"energy_session"\n'
        '"ASK";"u1";"s2";2020-01-02 08:00:00;2020-01-02 10:00:00;2,5;10,25\n'
        '"ASK";"u1";"s1";2020-01-01 07:00:00;;;\n'
        '"ASK";"u2";"s1";2020-01-03 07:00:00;2020-01-03 08:00:00;1,0;5,0\n'
        '"ASK";"u1";"s3";bad;2020-01-03 08:00:00;1,0;5,0\n'
    )
    (raw / "Dataset1_charging_reports.csv").write_text(text)


def _azure_snapshot(root):
    import sqlite3
    import tempfile
    import zipfile as _z

    raw = root / "azure_packing_2020" / ev.AZURE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "packing_trace_zone_a_v1.sqlite"
        con = sqlite3.connect(db)
        con.execute(
            "CREATE TABLE vm (vmId INT, tenantId INT, vmTypeId INT, "
            "priority INT, starttime REAL, endtime REAL)"
        )
        con.executemany(
            "INSERT INTO vm VALUES (?, ?, ?, ?, ?, ?)",
            [
                (2, 100, 8, 1, 2.0, 5.0),
                (1, 100, 4, 0, 1.0, None),
                (3, 101, 4, 0, 1.0, 2.0),
                (4, 200, 9, 0, 0.5, 3.0),
            ],
        )
        con.commit()
        con.close()
        with _z.ZipFile(raw / "AzurePackingTraceV1.zip", "w") as z:
            z.write(db, "packing_trace_zone_a_v1.sqlite")
            z.writestr("readme.txt", "ignored")


def _aoe_snapshot(root):
    import zipfile as _z

    raw = root / "zen_aoe_interactions" / ev.AOE_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    xes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<log xes.version="1.0">\n'
        "  <trace>\n"
        '    <string key="concept:name" value="t2"/>\n'
        '    <string key="player_id" value="p1"/>\n'
        '    <string key="match_id" value="m1"/>\n'
        '    <string key="strategy" value="Rush"/>\n'
        '    <string key="map_type" value="Arabia"/>\n'
        '    <string key="civilization" value="Franks"/>\n'
        '    <string key="civilization_category" value="Cavalry"/>\n'
        '    <float key="elo" value="1250.5"/>\n'
        "    <event>\n"
        '      <string key="concept:name" value="Build"/>\n'
        '      <date key="time:timestamp" value="2023-01-01T02:00:00+02:00"/>\n'
        '      <int key="amount" value="2"/>\n'
        '      <int key="win" value="1"/>\n'
        "    </event>\n"
        "  </trace>\n"
        "  <trace>\n"
        '    <string key="concept:name" value="t1"/>\n'
        "    <event>\n"
        '      <string key="concept:name" value="Queue"/>\n'
        '      <date key="time:timestamp" value="2023-01-01T00:01:00+00:00"/>\n'
        "    </event>\n"
        "  </trace>\n"
        "</log>\n"
    )
    with _z.ZipFile(raw / "aoe_xes_head.zip", "w", _z.ZIP_DEFLATED) as z:
        z.writestr("aoe_interaction_log_1_of_10.xes", xes)


def test_ev_charging_view_parses_comma_decimals_pseudonymises_dedupes_and_sorts():
    df = pd.DataFrame(
        {
            "location": ["ASK", "ASK", "ASK", "ASK"],
            "user_id": ["u1", "u1", "u2", "u1"],
            "session_id": ["s2", "s1", "s1", "s3"],
            "plugin_time": [
                "2020-01-02 08:00:00",
                "2020-01-01 07:00:00",
                "2020-01-03 07:00:00",
                "bad",
            ],  # noqa: E501
            "plugout_time": ["2020-01-02 10:00:00", None, "2020-01-03 08:00:00", None],
            "connection_time": ["2,5", None, "bad", "1,0"],
            "energy_session": ["10,25", "bad", "5,0", "1,0"],
        }
    )
    out = ev.ev_charging_view(df)
    assert out.columns.tolist() == [
        "session_id",
        "user_id",
        "location",
        "plugin_time",
        "plugout_time",
        "connection_hours",
        "energy_kwh",
    ]
    assert out["session_id"].tolist() == [ev.pseudonym("s1"), ev.pseudonym("s2")]
    assert out["user_id"].tolist() == [ev.pseudonym("u1"), ev.pseudonym("u1")]
    assert out["location"].tolist() == ["ASK", "ASK"]
    assert out["plugin_time"].tolist() == [
        pd.Timestamp("2020-01-01 07:00:00"),
        pd.Timestamp("2020-01-02 08:00:00"),
    ]
    assert out["plugout_time"].iloc[1] == pd.Timestamp("2020-01-02 10:00:00")
    assert pd.isna(out["connection_hours"].iloc[0]) and out["connection_hours"].iloc[1] == 2.5
    assert pd.isna(out["energy_kwh"].iloc[0]) and out["energy_kwh"].iloc[1] == 10.25
    assert pd.isna(out["plugout_time"].iloc[0])
    assert out.attrs == {"duplicates": 1, "unreadable_timestamps": 1}


def test_ev_charging_builder_writes_csv_manifest_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no EV charging file in the snapshot$"):
        ev._build_ev_charging(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _ev_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_ev_charging(root, out, manifest)
    ev._build_ev_charging(root, out, manifest)
    target = out / "zen_ev_charging" / "sessions.csv"
    lines = target.read_text().splitlines()
    assert lines[0] == (
        "session_id,user_id,location,plugin_time,plugout_time,connection_hours,energy_kwh"
    )
    assert len(lines) == 3
    view = manifest["zen_ev_charging"]
    assert view["files"]["sessions.csv"]["rows"] == 2 and view["dropped"] == []
    assert view["pseudonymised"] == ["session_id", "user_id"] and view["salt_label"] == ev.SALT
    assert view["source_snapshot"] == f"zen_ev_charging/{ev.EV_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "locations": 1,
        "method": "complete Dataset1_charging_reports session log across 12 residential sites",
        "unreadable_timestamps": 1,
        "users": 1,
    }


def test_azure_packing_view_filters_multi_vm_tenants_orders_and_numbers_positions():
    df = pd.DataFrame(
        {
            "vmId": [20, 10, 30, 5],
            "tenantId": [100, 100, 200, 100],
            "vmTypeId": [8, 4, 9, 4],
            "priority": [1, 0, 0, 1],
            "starttime": [2.0, 2.0, 1.0, 1.0],
            "endtime": [5.0, 6.0, 3.0, None],
        }
    )
    out = ev.azure_packing_view(df)
    assert out.columns.tolist() == [
        "tenant_id",
        "position",
        "starttime",
        "endtime",
        "vm_id",
        "vm_type_id",
        "priority",
    ]
    assert out["tenant_id"].tolist() == [100, 100, 100]
    assert out["starttime"].tolist() == [1.0, 2.0, 2.0]
    assert pd.isna(out["endtime"].iloc[0]) and out["endtime"].iloc[1:].tolist() == [6.0, 5.0]
    assert out["vm_id"].tolist() == [5, 10, 20]
    assert out["vm_type_id"].tolist() == [4, 4, 8]
    assert out["priority"].tolist() == [1, 0, 1]
    assert out["position"].tolist() == [0, 1, 2]
    assert out.attrs == {"single_vm_rows_dropped": 1}


def test_azure_packing_builder_reads_sqlite_zip_and_errors_when_missing(tmp_path, monkeypatch):
    with pytest.raises(ev.ViewError, match=r"^no Azure packing zip archive in the snapshot$"):
        ev._build_azure_packing(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _azure_snapshot(root)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_azure_packing(root, out, manifest)
    ev._build_azure_packing(root, out, manifest)
    assert list(cwd.iterdir()) == []
    target = out / "azure_packing_2020" / "allocations.csv"
    lines = target.read_text().splitlines()
    assert lines[0] == "tenant_id,position,starttime,endtime,vm_id,vm_type_id,priority"
    assert len(lines) == 3
    view = manifest["azure_packing_2020"]
    assert view["files"]["allocations.csv"]["rows"] == 2
    assert view["dropped"] == ["vmType hardware dimensions", "single-VM tenants"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"azure_packing_2020/{ev.AZURE_SNAPSHOT}"
    assert view["sampling"] == {
        "method": "deterministic 1-in-100 tenant slice (tenantId % 100 == 0) limited to multi-VM tenants ordered by relative starttime",  # noqa: E501
        "modulo": ev.AZURE_MODULO,
        "single_vm_rows_dropped": 1,
        "tenants": 1,
    }


def test_aoe_interactions_view_pseudonymises_parses_utc_and_coerces_numbers():
    traces = [
        {
            "case": "t2",
            "attributes": {
                "player_id": "p1",
                "match_id": "m1",
                "strategy": "Rush",
                "map_type": "Arabia",
                "civilization": "Franks",
                "civilization_category": "Cavalry",
                "elo": "1250.5",
            },
            "events": [
                {
                    "concept:name": "Build",
                    "time:timestamp": "2023-01-01T02:00:00+02:00",
                    "amount": "2",
                    "win": "1",
                },
                {
                    "concept:name": "Bad",
                    "time:timestamp": "not-a-date",
                    "amount": "bad",
                    "win": "bad",
                },
            ],
        },
        {
            "case": "t1",
            "attributes": {"elo": "bad"},
            "events": [
                {
                    "concept:name": "Queue",
                    "time:timestamp": "2023-01-01T00:01:00+00:00",
                }
            ],
        },
    ]
    out = ev.aoe_interactions_view(traces)
    assert out.columns.tolist() == list(ev.AOE_COLUMNS)
    assert out["case_id"].tolist() == sorted(
        [ev.pseudonym("t1"), ev.pseudonym("t2"), ev.pseudonym("t2")]
    )
    t2_rows = out[out["case_id"] == ev.pseudonym("t2")]
    assert t2_rows["position"].tolist() == [0, 1]
    assert t2_rows["time"].iloc[0] == pd.Timestamp("2023-01-01 00:00:00")
    assert pd.isna(t2_rows["time"].iloc[1]) and pd.isna(t2_rows["amount"].iloc[1])
    assert pd.isna(t2_rows["win"].iloc[1])
    assert t2_rows["action"].tolist() == ["Build", "Bad"]
    assert t2_rows["amount"].iloc[0] == 2.0 and t2_rows["win"].iloc[0] == 1.0
    assert t2_rows["elo"].iloc[0] == 1250.5
    assert t2_rows["strategy"].tolist() == ["Rush", "Rush"]
    assert t2_rows["map_type"].tolist() == ["Arabia", "Arabia"]
    assert t2_rows["civilization"].tolist() == ["Franks", "Franks"]
    assert t2_rows["civilization_category"].tolist() == ["Cavalry", "Cavalry"]
    assert t2_rows["player_id"].iloc[0] == ev.pseudonym("p1")
    assert t2_rows["match_id"].iloc[0] == ev.pseudonym("m1")
    t1_row = out[out["case_id"] == ev.pseudonym("t1")].iloc[0]
    assert pd.isna(t1_row["player_id"]) and pd.isna(t1_row["match_id"]) and pd.isna(t1_row["elo"])
    assert pd.isna(t1_row["win"]) and pd.isna(t1_row["strategy"]) and pd.isna(t1_row["map_type"])
    assert pd.isna(t1_row["civilization"]) and pd.isna(t1_row["civilization_category"])
    assert t1_row["action"] == "Queue" and t1_row["position"] == 0


def test_aoe_builder_decodes_zip_prefix_writes_csv_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no AoE XES prefix archive in the snapshot$"):
        ev._build_aoe(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _aoe_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_aoe(root, out, manifest)
    ev._build_aoe(root, out, manifest)
    target = out / "zen_aoe_interactions" / "events.csv"
    lines = target.read_text().splitlines()
    assert lines[0] == ",".join(ev.AOE_COLUMNS) and len(lines) == 3
    view = manifest["zen_aoe_interactions"]
    assert view["files"]["events.csv"]["rows"] == 2
    assert view["dropped"] == [] and view["salt_label"] == ev.SALT
    assert view["pseudonymised"] == ["case_id", "player_id", "match_id"]
    assert view["source_snapshot"] == f"zen_aoe_interactions/{ev.AOE_SNAPSHOT}"
    assert view["sampling"] == {
        "member": "aoe_interaction_log_1_of_10.xes",
        "method": "4 MiB compressed zip-prefix of Age of Empires interaction log decoded via xes_stream",  # noqa: E501
        "status": {
            "bytes_in": 866,
            "bytes_out": 866,
            "modulo": 1,
            "stop": "log_closed",
            "stream_complete": True,
            "traces_kept": 2,
            "traces_seen": 2,
            "traces_without_case": 0,
        },
        "traces": 2,
    }


def _charity_raw_tables():
    tables = {}
    for name, rule in ev.CHARITY_SPEC["tables"].items():
        cols = rule["keep"]
        r1 = {c: f"1_{c}" for c in cols}
        r2 = {c: f"2_{c}" for c in cols}
        r1["organisation_number"] = "20"
        r2["organisation_number"] = "21"
        rows = [r2, r1]
        if name != "charity":
            r3 = {c: f"3_{c}" for c in cols}
            r3["organisation_number"] = "40"
            r4 = {c: f"4_{c}" for c in cols}
            r4["organisation_number"] = "bad"
            rows = [r2, r3, r1, r4]
        else:
            r1["charity_name"] = "Hidden"
            r1["charity_activities"] = "a," * 30 + 'say "unbalanced'
            r2["charity_name"] = "Odd"
            r2["charity_activities"] = "plain"
        tables[name] = pd.DataFrame(rows)
    return tables


def _charity_snapshot(root):
    import zipfile as _z

    raw = root / "uk_charity_register" / ev.CHARITY_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    for name, frame in _charity_raw_tables().items():
        zname = ev.CHARITY_FILES[name]
        lines = ["\t".join(frame.columns)]
        for row in frame.to_dict(orient="records"):
            lines.append("\t".join(str(row[c]) for c in frame.columns))
        with _z.ZipFile(raw / zname, "w") as z:
            z.writestr(f"publicextract.{name}.txt", "\n".join(lines) + "\n")


def _japan_raw_tables():
    tables = {}
    for name, rule in ev.JAPAN_SPEC["tables"].items():
        cols = rule["keep"]
        r1 = {c: "010" for c in cols}
        r2 = {c: "20" for c in cols}
        if name == "designers":
            r1["name_ja"] = "Person Name"
            r2["name_ja"] = "Corp Name"
        elif name == "sources":
            r1["authors"] = "Author Name"
            r2["authors"] = "Editor Name"
        elif name == "buildings":
            r1["archaeological_evidence_site_id"] = "010"
            r2["archaeological_evidence_site_id"] = None
            r1["rebuild_notes"] = "note"
            r2["rebuild_notes"] = "note2"
        tables[name] = pd.DataFrame([r2, r1])
    return tables


def _japan_snapshot(root):
    import zipfile as _z

    raw = root / "zen_japan_buildings" / ev.JAPAN_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    with _z.ZipFile(raw / "reconstructed_buildings_japan_v1.1.zip", "w") as z:
        for name, frame in _japan_raw_tables().items():
            z.writestr(f"{ev.JAPAN_PREFIX}{name}.csv", frame.to_csv(index=False))


def test_charity_register_view_filters_modulo_drops_pii_sorts_and_counts_orphans():
    tables = _charity_raw_tables()
    views, rels = ev.charity_register_view(tables, modulo=20)
    assert set(views) == set(ev.CHARITY_FILES)
    assert list(views["charity"].columns) == ev.CHARITY_SPEC["tables"]["charity"]["keep"]
    assert views["charity"].index.tolist() == [0]
    assert "charity_name" not in views["charity"]
    assert "charity_activities" not in views["charity"]
    assert views["charity"]["organisation_number"].tolist() == ["20"]
    assert views["classification"]["organisation_number"].tolist() == ["20", "40"]
    assert rels == [
        {
            "child": "annual_return_history.organisation_number",
            "parent": "charity.organisation_number",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
        {
            "child": "area_of_operation.organisation_number",
            "parent": "charity.organisation_number",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
        {
            "child": "classification.organisation_number",
            "parent": "charity.organisation_number",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
        {
            "child": "event_history.organisation_number",
            "parent": "charity.organisation_number",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
    ]


def test_charity_register_builder_reads_zips_writes_csvs_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no UK charity zip "):
        ev._build_charity_register(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _charity_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_charity_register(root, out, manifest)
    ev._build_charity_register(root, out, manifest)
    view = manifest["uk_charity_register"]
    assert view["files"]["charity.csv"]["rows"] == 1
    assert view["files"]["classification.csv"]["rows"] == 2
    assert (out / "uk_charity_register" / "charity.csv").read_text().splitlines()[0] == ",".join(
        ev.CHARITY_SPEC["tables"]["charity"]["keep"]
    )
    assert view["pseudonymised"] == []
    assert view["dropped"] == [
        "charity_name",
        "charity_contact_*",
        "charity_activities",
        "reason",
        "assoc_charity_name",
        "trustee table (not downloaded)",
    ]
    assert view["source_snapshot"] == f"uk_charity_register/{ev.CHARITY_SNAPSHOT}"
    assert view["sampling"] == {
        "method": f"deterministic 1-in-{ev.CHARITY_MODULO} slice on organisation_number across 5 non-trustee extracts",  # noqa: E501
        "modulo": ev.CHARITY_MODULO,
    }
    assert len(view["relations"]) == 4 and all(r["orphans"] == 1 for r in view["relations"])


def test_japan_buildings_view_drops_pii_sorts_and_audits_six_relations():
    tables = _japan_raw_tables()
    tables["building_designers"] = pd.concat(
        [tables["building_designers"], pd.DataFrame([{"building_id": "010", "designer_id": "999"}])]
    )
    views, rels = ev.japan_buildings_view(tables)
    assert set(views) == set(ev.JAPAN_SPEC["tables"])
    assert list(views["buildings"].columns) == ev.JAPAN_SPEC["tables"]["buildings"]["keep"]
    assert views["buildings"].index.tolist() == [0, 1]
    assert "name_ja" not in views["designers"] and "authors" not in views["sources"]
    assert "rebuild_notes" not in views["buildings"]
    assert views["buildings"]["building_id"].tolist() == ["010", "20"]
    by_child = {r["child"]: r for r in rels}
    assert by_child["buildings.archaeological_evidence_site_id"]["checked"] == 1
    assert by_child["buildings.archaeological_evidence_site_id"]["orphans"] == 0
    assert by_child["building_designers.designer_id"]["checked"] == 3
    assert by_child["building_designers.designer_id"]["orphans"] == 1


def test_japan_buildings_builder_reads_zip_writes_csvs_and_errors_when_missing(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no Japan buildings zip archive in the snapshot$"):
        ev._build_japan_buildings(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _japan_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_japan_buildings(root, out, manifest)
    ev._build_japan_buildings(root, out, manifest)
    view = manifest["zen_japan_buildings"]
    assert len(view["files"]) == 7 and view["files"]["buildings.csv"]["rows"] == 2
    lines = (out / "zen_japan_buildings" / "designers.csv").read_text().splitlines()
    assert lines[0] == "designer_id,is_individual,primary_designer_type_id"
    assert lines[1].startswith("010,")
    assert view["pseudonymised"] == []
    assert view["dropped"] == [
        "designer personal/company names, affiliations and URLs",
        "source authors, titles and URLs",
        "site street addresses and postal codes",
        "free-text notes",
    ]
    assert view["source_snapshot"] == f"zen_japan_buildings/{ev.JAPAN_SNAPSHOT}"
    assert view["sampling"] == {
        "method": "complete core 7-table relational schema (no row sampling)"
    }
    assert len(view["relations"]) == 6 and all(r["orphans"] == 0 for r in view["relations"])


def _coops_snapshot(root):
    raw = root / "noaa_coops_tides" / ev.COOPS_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "coops_8518750_2022.json").write_text(
        json.dumps(
            {
                "metadata": {"id": "8518750"},
                "data": [
                    {"t": "2022-01-01 01:00", "v": "0.80", "s": "0.02", "f": "1,1"},
                    {"t": "2022-01-01 00:00", "v": "0.50", "s": "0.01", "f": "0,0"},
                    {"t": "2022-01-01 00:00", "v": "9.99", "s": "0.01", "f": "0,0"},
                    {"t": "bad-time", "v": "0.10", "s": "0.01", "f": "0,0"},
                ],
            }
        )
    )
    (raw / "coops_9414290_2022.json").write_text(
        json.dumps(
            {
                "metadata": {"id": "9414290"},
                "data": [{"t": "2022-01-01 00:00", "v": "", "s": "0.0", "f": "1,0"}],
            }
        )
    )


def _gml_co2_snapshot(root):
    raw = root / "noaa_gml_co2_weekly" / ev.GML_CO2_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "co2_weekly_mlo.csv").write_text(
        "# comment header\n"
        "year,month,day,decimal,average,ndays,1 year ago,10 years ago,increase since 1800\n"
        "2020,1,12,2020.0301,-999.99,0,-999.99,-999.99,-999.99\n"
        "2020,1,5,2020.0110,413.5,6,410.1,390.2,135.4\n"
        "bad,1,1,2020.0,400.0,1,400.0,400.0,100.0\n"
    )


def _cnc_snapshot(root):
    raw = root / "zen_cnc_milling" / ev.CNC_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    base = {c: 1.0 for c in ev.CNC_SIGNALS}
    r1 = {"Unnamed: 0": 0, "DateTime": "2022-04-05 13:06:13", **base, "ToolNumber": 2.0, "Phase": 7}
    r2 = {"Unnamed: 0": 1, "DateTime": "2022-04-05 13:06:11", **base, "ToolNumber": 1.0, "Phase": 7}
    r_dup = {
        "Unnamed: 0": 2,
        "DateTime": "2022-04-05 13:06:11",
        **base,
        "ToolNumber": 9.0,
        "Phase": 7,
    }
    r_bad = {"Unnamed: 0": 3, "DateTime": "bad", **base, "ToolNumber": 3.0, "Phase": 7}
    pd.DataFrame([r1, r2, r_dup, r_bad]).to_csv(raw / "Data_from_2022-04.csv", index=False)
    r3 = {"DateTime": "2021-11-26 07:15:36", **base, "ToolNumber": "bad", "PocketTable": 5}
    pd.DataFrame([r3]).to_csv(raw / "Data_from_2021-11-26.csv", index=False)


def test_coops_tides_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no NOAA CO-OPS JSON files in the snapshot$"):
        ev._build_coops_tides(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _coops_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_coops_tides(root, out, manifest)
    ev._build_coops_tides(root, out, manifest)
    df = pd.read_csv(out / "noaa_coops_tides" / "tides.csv", dtype={"station_id": str})
    assert df.columns.tolist() == ["station_id", "timestamp", "water_level_m", "sigma_m", "flags"]
    assert df["station_id"].tolist() == ["8518750", "8518750", "9414290"]
    assert df["water_level_m"].iloc[0] == 0.5
    assert df["sigma_m"].tolist() == [0.01, 0.02, 0.0]
    assert pd.isna(df["water_level_m"].iloc[2])
    empty, dups0 = ev.coops_tides_view([])
    assert len(empty) == 0 and dups0 == 0
    assert empty.columns.tolist() == [
        "station_id",
        "timestamp",
        "water_level_m",
        "sigma_m",
        "flags",
    ]
    bad, _ = ev.coops_tides_view(
        [
            {"station_id": "1", "t": "2022/01/01 00:00", "v": "1.0", "s": "0.1", "f": "0,0"},
            {"station_id": "1", "t": "2022-01-01 00:00", "v": "bad", "s": "bad", "f": "0,0"},
        ]
    )
    assert len(bad) == 1
    assert pd.isna(bad["water_level_m"].iloc[0]) and pd.isna(bad["sigma_m"].iloc[0])
    nodata_root = tmp_path / "nodata_acq"
    _coops_snapshot(nodata_root)
    (nodata_root / "noaa_coops_tides" / ev.COOPS_SNAPSHOT / "raw" / "coops_0_2022.json").write_text(
        json.dumps({"metadata": {"id": "0"}})
    )
    m_nodata: dict = {}
    ev._build_coops_tides(nodata_root, tmp_path / "nodata_out", m_nodata)
    assert m_nodata["noaa_coops_tides"]["files"]["tides.csv"]["rows"] == 3
    view = manifest["noaa_coops_tides"]
    assert view["dropped"] == [] and view["pseudonymised"] == []
    assert view["source_snapshot"] == f"noaa_coops_tides/{ev.COOPS_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "first_timestamp": "2022-01-01 00:00:00",
        "flagged_rows": 2,
        "last_timestamp": "2022-01-01 01:00:00",
        "method": "six US coastal stations hourly water level (2022-2024 GMT)",
        "missing_value_rows": 1,
        "stations": 2,
    }


def test_gml_co2_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no NOAA GML CO2 file in the snapshot$"):
        ev._build_gml_co2(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _gml_co2_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_gml_co2(root, out, manifest)
    ev._build_gml_co2(root, out, manifest)
    df = pd.read_csv(out / "noaa_gml_co2_weekly" / "co2_weekly.csv")
    assert df.columns.tolist() == [
        "timestamp",
        "decimal_year",
        "co2_ppm",
        "one_year_ago_ppm",
        "ten_years_ago_ppm",
        "increase_since_1800_ppm",
        "ndays",
    ]
    assert df["timestamp"].tolist() == ["2020-01-05", "2020-01-12"]
    assert df["co2_ppm"].iloc[0] == 413.5 and df["ndays"].tolist() == [6, 0]
    for col in ("co2_ppm", "one_year_ago_ppm", "ten_years_ago_ppm", "increase_since_1800_ppm"):
        assert pd.isna(df[col].iloc[1])
    view = manifest["noaa_gml_co2_weekly"]
    assert view["source_snapshot"] == f"noaa_gml_co2_weekly/{ev.GML_CO2_SNAPSHOT}"
    assert view["sampling"] == {
        "first_timestamp": "2020-01-05 00:00:00",
        "last_timestamp": "2020-01-12 00:00:00",
        "method": "complete weekly Mauna Loa atmospheric CO2 record (1974-2026)",
        "missing_co2_rows": 1,
    }


def test_cnc_milling_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no CNC milling CSV files in the snapshot$"):
        ev._build_cnc_milling(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _cnc_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_cnc_milling(root, out, manifest)
    ev._build_cnc_milling(root, out, manifest)
    df = pd.read_csv(out / "zen_cnc_milling" / "cnc_milling.csv", dtype={"series_id": str})
    assert df.columns.tolist() == ["series_id", "timestamp", *ev.CNC_SIGNALS]
    assert df["series_id"].tolist() == ["2021-11-26", "2022-04", "2022-04"]
    assert df["ToolNumber"].iloc[1] == 1.0 and pd.isna(df["ToolNumber"].iloc[0])
    view = manifest["zen_cnc_milling"]
    assert view["dropped"] == ["Unnamed: 0", "Phase", "Phase_compressed", "PocketTable"]
    assert view["pseudonymised"] == []
    assert view["source_snapshot"] == f"zen_cnc_milling/{ev.CNC_SNAPSHOT}"
    assert view["sampling"] == {
        "duplicates_dropped": 1,
        "first_timestamp": "2021-11-26 07:15:36",
        "last_timestamp": "2022-04-05 13:06:13",
        "method": "complete 13-file five-axis CNC production series telemetry (Nov 2021 - Apr 2022)",  # noqa: E501
        "series_count": 2,
        "series_files": 2,
    }


def _wb_snapshot(root):
    raw = root / "wb_lending_projects" / ev.WB_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "wb_projects_p0.json").write_text(
        json.dumps(
            {
                "projects": {
                    "P2": {
                        "id": "P2",
                        "boardapprovaldate": "2024-01-01T00:00:00Z",
                        "closingdate": None,
                        "approvalfy": "2024",
                        "countrycode": ["FR"],
                        "regionname": "ECA",
                        "lendinginstr": "IPF",
                        "lendinginstrtype": "IN",
                        "prodline": "PE",
                        "status": "Active",
                        "curr_total_commitment": "1,500",
                        "curr_ibrd_commitment": "1000",
                        "curr_ida_commitment": "500",
                        "grantamt": None,
                        "lendprojectcost": "2,000,000",
                        "sector1": {"Name": "Energy", "Percent": 100},
                        "teamleadname": "Alice Doe",
                        "project_name": "Grid",
                    },
                    "P1": {
                        "id": "P1",
                        "approvalfy": "bad",
                        "countrycode": [],
                        "sector1": "bad",
                    },
                    "P_DUP": {"id": "P2", "approvalfy": "2020"},
                    "P_NONE": {"approvalfy": "2020"},
                }
            }
        )
    )
    (raw / "wb_projects_p1.json").write_text(json.dumps({}))


def _qld_snapshot(root):
    raw = root / "zen_queensland_petrol" / ev.QLD_PETROL_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    base = {c: "1.5" for c in ev.QLD_NUM_COLS}
    r1 = {
        "reporting_period": "2025-12-31",
        "production_type": "GAS",
        "authorized_holder": "Corp B",
        "permit_number": "PL 2",
        "basin": "BOWEN",
        "reservoir_unit_name": "U2",
        "strat_unit_name": "S2",
        "secondary_strat_unit_name": "",
        "field_name": "F2",
        "remark": "note",
        "field_name_prod_corr": "F2",
        **base,
    }
    r2 = {**r1, "reporting_period": "2025-06-30", "permit_number": "PL 1", "wells_on_prod": "bad"}
    pd.DataFrame([r1, r2]).to_csv(raw / "data.csv", index=False)


def _inpi_snapshot(root):
    raw = root / "inpi_bce_ratios" / ev.INPI_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    nums = {c: "10.5" for c in ev.INPI_NUM_COLS}
    r_pub1 = {
        "siren": "222222222",
        "date_cloture_exercice": "2024-12-31",
        "type_bilan": "C",
        "confidentiality": "Public",
        **nums,
    }
    r_pub2 = {
        "siren": "111111111",
        "date_cloture_exercice": "2023-12-31",
        "type_bilan": "S",
        "confidentiality": "Public",
        **nums,
        "ratio_de_vetuste": "bad",
    }
    r_priv = {
        "siren": "333333333",
        "date_cloture_exercice": "2024-12-31",
        "type_bilan": "C",
        "confidentiality": "Partiellement confidentiel",
        **nums,
    }
    pd.DataFrame([r_pub1, r_priv, r_pub2]).to_csv(
        raw / "ratios_inpi_bce_30k.csv", sep=";", index=False
    )


def test_wb_projects_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no World Bank project JSON files in the snapshot$"):
        ev._build_wb_projects(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _wb_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_wb_projects(root, out, manifest)
    ev._build_wb_projects(root, out, manifest)
    df = pd.read_csv(out / "wb_lending_projects" / "projects.csv")
    assert df["project_id"].tolist() == ["P1", "P2"]
    assert df.columns.tolist() == [
        "project_id",
        "board_approval_date",
        "closing_date",
        "approval_fy",
        "country_code",
        "region_name",
        "lending_instrument",
        "lending_instrument_type",
        "prodline",
        "status",
        "curr_total_commitment",
        "curr_ibrd_commitment",
        "curr_ida_commitment",
        "grant_amt",
        "lend_project_cost",
        "sector1_name",
        "sector1_percent",
    ]
    assert "teamleadname" not in df and "project_name" not in df
    row2 = df.iloc[1]
    assert row2["board_approval_date"] == "2024-01-01T00:00:00Z"
    assert pd.isna(row2["closing_date"]) and row2["approval_fy"] == 2024
    assert row2["country_code"] == "FR" and row2["region_name"] == "ECA"
    assert row2["lending_instrument"] == "IPF" and row2["lending_instrument_type"] == "IN"
    assert row2["prodline"] == "PE" and row2["status"] == "Active"
    assert row2["curr_ibrd_commitment"] == 1000.0 and row2["curr_ida_commitment"] == 500.0
    assert pd.isna(row2["grant_amt"])
    assert pd.isna(df["country_code"].iloc[0])
    assert df["lend_project_cost"].iloc[1] == 2000000.0
    assert df["curr_total_commitment"].iloc[1] == 1500.0
    assert df["sector1_name"].iloc[1] == "Energy" and df["sector1_percent"].iloc[1] == 100.0
    assert pd.isna(df["sector1_name"].iloc[0]) and pd.isna(df["approval_fy"].iloc[0])
    assert pd.isna(ev._num_clean(pd.Series(["bad"])).iloc[0])
    assert ev.wb_projects_view([]).empty
    view = manifest["wb_lending_projects"]
    assert view["dropped"] == ["teamleadname", "project_name", "projectdocs", "url"]
    assert view["pseudonymised"] == []
    assert view["sampling"]["pages"] == 2
    assert view["source_snapshot"] == f"wb_lending_projects/{ev.WB_SNAPSHOT}"


def test_queensland_petrol_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no Queensland petroleum CSV in the snapshot$"):
        ev._build_queensland_petrol(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _qld_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_queensland_petrol(root, out, manifest)
    ev._build_queensland_petrol(root, out, manifest)
    df = pd.read_csv(out / "zen_queensland_petrol" / "production.csv")
    assert df.columns.tolist() == [*ev.QLD_TEXT_COLS, *ev.QLD_NUM_COLS]
    assert df["reporting_period"].tolist() == ["2025-06-30", "2025-12-31"]
    assert pd.isna(df["wells_on_prod"].iloc[0]) and df["wells_on_prod"].iloc[1] == 1.5
    assert "authorized_holder" not in df and "remark" not in df
    lead_root = tmp_path / "lead_acq"
    lead_raw = lead_root / "zen_queensland_petrol" / ev.QLD_PETROL_SNAPSHOT / "raw"
    lead_raw.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                **{c: "007" for c in ev.QLD_TEXT_COLS},
                **{c: "1.0" for c in ev.QLD_NUM_COLS},
                "authorized_holder": "X",
            }
        ]
    ).to_csv(lead_raw / "data.csv", index=False)
    ev._build_queensland_petrol(lead_root, tmp_path / "lead_out", {})
    assert (
        (tmp_path / "lead_out" / "zen_queensland_petrol" / "production.csv")
        .read_text()
        .splitlines()[1]
        .startswith("007,007,007,")
    )
    view = manifest["zen_queensland_petrol"]
    assert view["dropped"] == [
        "authorized_holder",
        "remark",
        "secondary_strat_unit_name",
        "field_name_prod_corr",
    ]
    assert view["source_snapshot"] == f"zen_queensland_petrol/{ev.QLD_PETROL_SNAPSHOT}"


def test_inpi_ratios_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no INPI BCE ratios CSV in the snapshot$"):
        ev._build_inpi_ratios(tmp_path / "empty", tmp_path / "err", {})
    root = tmp_path / "acq"
    _inpi_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_inpi_ratios(root, out, manifest)
    ev._build_inpi_ratios(root, out, manifest)
    df = pd.read_csv(out / "inpi_bce_ratios" / "ratios.csv")
    assert df.columns.tolist() == [
        "siren_id",
        "date_cloture_exercice",
        "type_bilan",
        *ev.INPI_NUM_COLS,
    ]
    expected_ids = sorted([ev.pseudonym("111111111"), ev.pseudonym("222222222")])
    assert df["siren_id"].tolist() == expected_ids
    assert sorted(df["date_cloture_exercice"].tolist()) == ["2023-12-31", "2024-12-31"]
    assert sorted(df["type_bilan"].tolist()) == ["C", "S"]
    assert ev.pseudonym("333333333") not in df["siren_id"].tolist()
    assert pd.isna(df["ratio_de_vetuste"]).sum() == 1
    view = manifest["inpi_bce_ratios"]
    assert view["dropped"] == ["confidentiality"] and view["pseudonymised"] == ["siren"]
    assert view["salt_label"] == ev.SALT and view["sampling"]["non_public_dropped"] == 1
    assert view["source_snapshot"] == f"inpi_bce_ratios/{ev.INPI_SNAPSHOT}"
    edge_root = tmp_path / "edge_acq"
    edge_raw = edge_root / "inpi_bce_ratios" / ev.INPI_SNAPSHOT / "raw"
    edge_raw.mkdir(parents=True)
    nums = {c: "1" for c in ev.INPI_NUM_COLS}
    cols = ["siren", "date_cloture_exercice", "type_bilan", "confidentiality", *ev.INPI_NUM_COLS]
    row_a = {
        "siren": "001",
        "date_cloture_exercice": "2024-12-31",
        "type_bilan": "," * 30,
        "confidentiality": "Public",
        **nums,
    }
    (edge_raw / "ratios_inpi_bce_30k.csv").write_text(
        ";".join(cols) + "\n" + ";".join(row_a[c] for c in cols) + "\n"
    )
    ev._build_inpi_ratios(edge_root, tmp_path / "edge_out", {})
    assert pd.read_csv(tmp_path / "edge_out" / "inpi_bce_ratios" / "ratios.csv")["siren_id"].iloc[
        0
    ] == ev.pseudonym("001")
    blank, _ = ev.inpi_ratios_view(
        pd.DataFrame(
            [
                {
                    "siren": None,
                    "date_cloture_exercice": "2024",
                    "type_bilan": "C",
                    "confidentiality": "Public",
                    **{c: "1" for c in ev.INPI_NUM_COLS},
                }
            ]
        )
    )
    assert blank["siren_id"].tolist() == [""]


def _ror_snapshot(root):
    import zipfile

    raw = root / "ror_organizations" / ev.ROR_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    records = [
        {"id": "https://ror.org/02", "names": [{"value": "Uni B"}], "contact": "a@uni.org"},
        {"id": "https://ror.org/01", "names": [{"value": "Uni A"}]},
        {"id": "https://ror.org/01", "names": [{"value": "Uni A dup"}]},
    ]
    with zipfile.ZipFile(raw / "ror_data.zip", "w") as zf:
        zf.writestr("notes.txt", "ignore")
        zf.writestr("v2-ror.json", json.dumps(records))


def _rcsb_snapshot(root):
    raw = root / "rcsb_pdb_entries" / ev.RCSB_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "entries_b01.json").write_text(
        json.dumps(
            {
                "data": {
                    "entries": [
                        {"rcsb_id": "8CMX", "struct": {"title": "Mail x@y.org"}, "b": 1, "a": 2},
                        {"rcsb_id": "7YBF", "struct": {"title": "Dup entry"}},
                    ]
                }
            }
        )
    )
    (raw / "entries_b00.json").write_text(
        json.dumps(
            {
                "data": {
                    "entries": [
                        {"rcsb_id": "7YBF", "struct": {"title": "First entry"}},
                    ]
                }
            }
        )
    )


def _nws_snapshot(root):
    raw = root / "nws_weather_alerts" / ev.NWS_SNAPSHOT / "raw"
    raw.mkdir(parents=True)
    (raw / "alerts_p2.json").write_text(
        json.dumps(
            {
                "features": [
                    {
                        "id": "u2",
                        "properties": {
                            "id": "NWS-2",
                            "sender": "w-nws.webmaster@noaa.gov",
                            "description": "Ask ops@noaa.gov",
                            "references": [{"id": "ref1", "sender": "sub@noaa.gov"}],
                        },
                    },
                    {"id": "u1", "properties": {"id": "NWS-1", "event": "Second"}},
                ]
            }
        )
    )
    (raw / "alerts_p1.json").write_text(
        json.dumps(
            {
                "features": [
                    {
                        "id": "u1",
                        "properties": {"id": "NWS-1", "sender": "drop@noaa.gov", "event": "First"},
                    }
                ]
            }
        )
    )


def test_ror_view_and_builder(tmp_path):
    import zipfile

    with pytest.raises(ev.ViewError, match=r"^no ROR zip archive in the snapshot$"):
        ev._build_ror(tmp_path / "empty", tmp_path / "err", {})
    no_json_root = tmp_path / "no_json"
    no_json_raw = no_json_root / "ror_organizations" / ev.ROR_SNAPSHOT / "raw"
    no_json_raw.mkdir(parents=True)
    with zipfile.ZipFile(no_json_raw / "ror_data.zip", "w") as zf:
        zf.writestr("readme.txt", "text")
    with pytest.raises(ev.ViewError, match=r"^no ROR JSON member in the archive$"):
        ev._build_ror(no_json_root, tmp_path / "err2", {})

    raw_recs = [
        {"id": "https://ror.org/03", "note": "c@ex.org"},
        {"id": "https://ror.org/01", "note": "first"},
        {"id": "https://ror.org/01", "note": "dup"},
        {"id": "https://ror.org/02", "note": "mid"},
    ]
    raw_copy = json.loads(json.dumps(raw_recs))
    assert [r["id"] for r in ev.ror_view(raw_recs, stride=2)] == [
        "https://ror.org/01",
        "https://ror.org/03",
    ]
    assert raw_recs == raw_copy
    default_out = ev.ror_view(raw_recs)
    assert [r["id"] for r in default_out] == ["https://ror.org/01"] and default_out[0][
        "note"
    ] == "first"

    root = tmp_path / "acq"
    _ror_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_ror(root, out, manifest)
    ev._build_ror(root, out, manifest)
    target = out / "ror_organizations" / "organizations.jsonl"
    raw_txt = target.read_text()
    assert raw_txt.endswith("\n") and raw_txt.splitlines() == [
        json.dumps({"id": "https://ror.org/01", "names": [{"value": "Uni A"}]}, sort_keys=True)
    ]
    view = manifest["ror_organizations"]
    assert view["dropped"] == [] and view["pseudonymised"] == []
    assert view["files"]["organizations.jsonl"]["rows"] == 1
    assert view["sampling"] == {
        "method": "every 15th ROR v2 organization record in canonical id order across all statuses",
        "total_records": 3,
        "stride": ev.ROR_STRIDE,
        "kept": 1,
    }
    assert view["source_snapshot"] == f"ror_organizations/{ev.ROR_SNAPSHOT}"


def test_rcsb_pdb_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no RCSB PDB entry files in the snapshot$"):
        ev._build_rcsb_pdb(tmp_path / "empty", tmp_path / "err", {})
    raw_entries = [
        {"rcsb_id": "8CMX", "note": "mail a@pdb.org"},
        {"rcsb_id": "7YBF", "title": "keep"},
        {"rcsb_id": "7YBF", "title": "dup"},
    ]
    raw_copy = json.loads(json.dumps(raw_entries))
    viewed = ev.rcsb_pdb_view(raw_entries)
    assert raw_entries == raw_copy
    assert [e["rcsb_id"] for e in viewed] == ["7YBF", "8CMX"]
    assert viewed[0]["title"] == "keep" and viewed[1]["note"] == "mail [email]"

    root = tmp_path / "acq"
    _rcsb_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_rcsb_pdb(root, out, manifest)
    ev._build_rcsb_pdb(root, out, manifest)
    target = out / "rcsb_pdb_entries" / "entries.jsonl"
    raw_txt = target.read_text()
    lines = raw_txt.splitlines()
    assert raw_txt.endswith("\n") and lines == [
        json.dumps({"rcsb_id": "7YBF", "struct": {"title": "First entry"}}, sort_keys=True),
        json.dumps(
            {"a": 2, "b": 1, "rcsb_id": "8CMX", "struct": {"title": "Mail [email]"}}, sort_keys=True
        ),
    ]
    view = manifest["rcsb_pdb_entries"]
    assert view["dropped"] == [
        "audit_author (omitted in GraphQL query)",
        "citation authors (omitted in GraphQL query)",
    ]
    assert view["pseudonymised"] == [] and view["files"]["entries.jsonl"]["rows"] == 2
    assert view["sampling"] == {
        "method": (
            "earliest released structures per calendar year ordered by initial_release_date "
            "and rcsb_id (2024:350, 2025:350, 2026:300)"
        ),
        "entries_in": 3,
        "files": ["entries_b00.json", "entries_b01.json"],
    }
    assert view["source_snapshot"] == f"rcsb_pdb_entries/{ev.RCSB_SNAPSHOT}"


def test_nws_alerts_view_and_builder(tmp_path):
    with pytest.raises(ev.ViewError, match=r"^no NWS alerts JSON in the snapshot$"):
        ev._build_nws_alerts(tmp_path / "empty", tmp_path / "err", {})
    raw_features = [
        {
            "properties": {
                "id": "A2",
                "sender": "drop@noaa.gov",
                "note": "u@noaa.gov",
                "references": [{"sender": "x@y.z"}],
            }
        },
        {"properties": {"id": "A1", "event": "keep"}},
        {"properties": {"id": "A1", "event": "dup"}},
    ]
    raw_copy = json.loads(json.dumps(raw_features))
    viewed = ev.nws_alerts_view(raw_features)
    assert raw_features == raw_copy
    assert [f["properties"]["id"] for f in viewed] == ["A1", "A2"]
    assert viewed[0]["properties"]["event"] == "keep"
    assert "sender" not in viewed[1]["properties"]
    assert "sender" not in viewed[1]["properties"]["references"][0]
    assert viewed[1]["properties"]["note"] == "[email]"

    root = tmp_path / "acq"
    _nws_snapshot(root)
    manifest: dict = {}
    out = tmp_path / "deep" / "out"
    ev._build_nws_alerts(root, out, manifest)
    ev._build_nws_alerts(root, out, manifest)
    target = out / "nws_weather_alerts" / "alerts.jsonl"
    raw_txt = target.read_text()
    lines = raw_txt.splitlines()
    assert raw_txt.endswith("\n") and lines == [
        json.dumps({"id": "u1", "properties": {"event": "First", "id": "NWS-1"}}, sort_keys=True),
        json.dumps(
            {
                "id": "u2",
                "properties": {
                    "description": "Ask [email]",
                    "id": "NWS-2",
                    "references": [{"id": "ref1"}],
                },
            },
            sort_keys=True,
        ),
    ]
    view = manifest["nws_weather_alerts"]
    assert view["dropped"] == ["sender"] and view["pseudonymised"] == []
    assert view["files"]["alerts.jsonl"]["rows"] == 2
    assert view["sampling"] == {
        "method": "four consecutive 500-alert cursor pages from NWS alerts API",
        "features_in": 3,
        "unique_alerts": 2,
        "files": ["alerts_p1.json", "alerts_p2.json"],
    }
    assert view["source_snapshot"] == f"nws_weather_alerts/{ev.NWS_SNAPSHOT}"
