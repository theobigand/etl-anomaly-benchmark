import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import readiness as rd  # noqa: E402


def full(**over):
    facts = {
        "id": "x:1",
        "source": "https://example.org",
        "licence_class": "open",
        "upstream_status": "verified",
        "files_verified": True,
        "structure_passed": True,
        "independent_group": "g",
        "privacy": "not_needed",
        "baseline_properties": [],
        "anomaly_origin": "controlled_injection",
        "units": 5000,
        "min_units": 1000,
        "protocol_id": "P-REL",
        "detection_unit": "row",
        "partitions": "70/15/15 chronological",
        "view_sha256": "ab" * 32,
        "view_preprocessing": "views.py@abc",
        "personal_fields_remaining": [],
    }
    facts.update(over)
    return facts


def test_a_complete_dataset_reaches_experiment_ready():
    assert rd.assess(full())["status"] == "experiment_ready"


def test_every_status_requires_the_previous_ones_and_names_what_failed():
    cases = {
        "discovered": full(source=None),
        "rights_verified": full(upstream_status="not_verified"),
        "acquired": full(files_verified=False),
        "structurally_valid": full(structure_passed=False),
        "scientifically_eligible": full(independent_group=None),
        "protocol_ready": full(protocol_id=None),
    }
    for stopped_at, facts in cases.items():
        result = rd.assess(facts)
        previous = (
            rd.STATUSES[rd.STATUSES.index(stopped_at) - 1] if stopped_at != "discovered" else None
        )
        assert result["status"] == previous
        assert result["failed"]["status"] == stopped_at and result["failed"]["reasons"]


def test_licence_class_and_privacy_and_size_gate_the_right_statuses():
    assert rd.assess(full(licence_class="unclear"))["status"] == "discovered"
    assert rd.assess(full(licence_class="research_only"))["status"] == "experiment_ready"
    assert rd.assess(full(privacy="unreviewed"))["status"] == "structurally_valid"
    assert rd.assess(full(units=10))["status"] == "structurally_valid"
    assert rd.assess(full(anomaly_origin=None))["status"] == "structurally_valid"
    assert rd.assess(full(personal_fields_remaining=["name"]))["status"] == "protocol_ready"
    assert rd.assess(full(view_sha256=None))["status"] == "protocol_ready"
    assert rd.assess(full(first_party=True, upstream_status=None))["status"] == "experiment_ready"


def test_summary_counts_datasets_reaching_each_status_and_groups_by_stratum():
    rows = [
        {"stratum": "C5", "status": "experiment_ready"},
        {"stratum": "C5", "status": "acquired"},
        {"stratum": "C6", "status": "protocol_ready"},
    ]
    table = rd.summarise(rows)
    assert table["C5"]["acquired"] == 2 and table["C5"]["experiment_ready"] == 1
    assert table["C6"]["protocol_ready"] == 1 and table["C6"]["experiment_ready"] == 0
    assert table["C6"]["discovered"] == 1


def test_facts_are_assembled_from_the_entry_the_declared_facts_and_the_view_manifest():
    entry = {
        "id": "a:1",
        "publisher": "pub",
        "stratum": "C5",
        "licence_class": "open",
        "eligible": True,
        "stages": {"data_acquired": True, "structural_validation": True},
    }
    declared = {
        "first_party": True,
        "independent_group": "g",
        "privacy": "handled",
        "baseline_properties": [],
        "anomaly_origin": "controlled_injection",
        "units": 5000,
        "min_units": 1000,
        "protocol_id": "P-REL",
        "partitions": "hash 70/15/15",
        "view": "v",
    }
    views = {"v": {"files": {"a.csv": {"sha256": "aa"}, "b.csv": {"sha256": "bb"}}}}
    protocols = {"P-REL": {"detection_unit": "relationship"}}
    facts = rd.facts_from(entry, declared, views, protocols)
    assert facts["detection_unit"] == "relationship" and len(facts["view_sha256"]) == 64
    assert rd.assess(facts)["status"] == "experiment_ready"
    no_view = rd.facts_from(entry, {**declared, "view": None}, views, protocols)
    assert rd.assess(no_view)["status"] == "protocol_ready"
    assert rd.facts_from(entry, None, views, protocols)["protocol_id"] is None
    ineligible = rd.facts_from({**entry, "eligible": False}, declared, views, protocols)
    assert rd.assess(ineligible)["status"] == "acquired"


def test_ready_groups_count_each_independent_group_once_per_stratum():
    rows = [
        {"stratum": "C4", "group": "loghub", "status": "experiment_ready"},
        {"stratum": "C4", "group": "loghub", "status": "experiment_ready"},
        {"stratum": "C4", "group": "other", "status": "protocol_ready"},
        {"stratum": "C5", "group": "oa", "status": "experiment_ready"},
    ]
    assert rd.ready_groups(rows) == {"C4": ["loghub"], "C5": ["oa"]}


# --- exact contracts of every check, of the assessment result and of the assembly ---------------


def test_every_check_returns_its_exact_reasons():
    assert rd.CHECKS["discovered"]({"id": "x", "source": "s"}) == []
    assert rd.CHECKS["discovered"]({"id": "x"}) == ["no identifier or source"]
    assert rd.CHECKS["discovered"]({"source": "s"}) == ["no identifier or source"]
    assert rd.CHECKS["rights_verified"]({"licence_class": "open", "first_party": True}) == []
    assert (
        rd.CHECKS["rights_verified"](
            {"licence_class": "research_only", "upstream_status": "verified"}
        )
        == []
    )
    assert rd.CHECKS["rights_verified"]({"licence_class": "restricted", "first_party": True}) == [
        "licence class 'restricted' is not open or research_only"
    ]
    assert rd.CHECKS["rights_verified"]({"licence_class": "open"}) == [
        "upstream terms not verified at the original publisher"
    ]
    assert rd.CHECKS["rights_verified"](
        {"licence_class": "open", "upstream_status": "not_verified"}
    ) == ["upstream terms not verified at the original publisher"]
    assert rd.CHECKS["rights_verified"]({}) == [
        "licence class None is not open or research_only",
        "upstream terms not verified at the original publisher",
    ]
    assert rd.CHECKS["acquired"]({"files_verified": True}) == []
    assert rd.CHECKS["acquired"]({}) == ["stored files not verified against checksums"]
    assert rd.CHECKS["structurally_valid"]({"structure_passed": True}) == []
    assert rd.CHECKS["structurally_valid"]({}) == ["structural validation not passed"]


def _eligible(**over):
    facts = {
        "independent_group": "g",
        "privacy": "handled",
        "baseline_properties": [],
        "anomaly_origin": "controlled_injection",
        "units": 10,
        "min_units": 10,
    }
    facts.update(over)
    return facts


def test_eligibility_reports_each_missing_element_with_its_own_reason():
    check = rd.CHECKS["scientifically_eligible"]
    assert check(_eligible()) == []
    assert check(_eligible(independent_group=None)) == ["no independent source group"]
    assert check(_eligible(privacy="unreviewed")) == ["personal-data handling not reviewed"]
    assert check(_eligible(privacy="not_needed")) == []
    assert check(_eligible(privacy=None)) == ["personal-data handling not reviewed"]
    missing = _eligible()
    del missing["baseline_properties"]
    assert check(missing) == ["expected source properties (baseline) not recorded"]
    assert check(_eligible(anomaly_origin=None)) == [
        "anomaly origin (natural or injected) not declared"
    ]
    assert check(_eligible(units=9)) == ["too few detection units"]
    assert check(_eligible(units=None)) == ["too few detection units"]
    assert check(_eligible(units=1, min_units=None)) == []  # no minimum declared: floor of one unit
    assert check(_eligible(units=0, min_units=None)) == ["too few detection units"]
    assert check({}) == [
        "no independent source group",
        "personal-data handling not reviewed",
        "expected source properties (baseline) not recorded",
        "anomaly origin (natural or injected) not declared",
        "too few detection units",
    ]


def test_protocol_and_view_checks_name_each_missing_element():
    protocol = rd.CHECKS["protocol_ready"]
    full = {"protocol_id": "P", "detection_unit": "row", "partitions": "x"}
    assert protocol(full) == []
    for key in full:
        assert protocol({**full, key: None}) == [f"{key} not defined"]
    assert protocol({}) == [
        "protocol_id not defined",
        "detection_unit not defined",
        "partitions not defined",
    ]
    view = rd.CHECKS["experiment_ready"]
    ready = {"view_sha256": "a", "view_preprocessing": "p", "personal_fields_remaining": []}
    assert view(ready) == []
    no_view = "no checksummed experimental view with recorded preprocessing"
    assert view({**ready, "view_sha256": None}) == [no_view]
    assert view({**ready, "view_preprocessing": None}) == [no_view]
    assert view({**ready, "personal_fields_remaining": ["name"]}) == [
        "personal fields remain in the experimental view"
    ]
    assert view({}) == [no_view]


def test_the_assessment_result_has_exactly_the_documented_shape():
    assert rd.assess(full()) == {"status": "experiment_ready", "failed": None}
    result = rd.assess(full(source=None))
    assert result == {
        "status": None,
        "failed": {"status": "discovered", "reasons": ["no identifier or source"]},
    }
    result = rd.assess(full(protocol_id=None))
    assert result["status"] == "scientifically_eligible"
    assert result["failed"] == {"status": "protocol_ready", "reasons": ["protocol_id not defined"]}
    assert rd.STATUSES == (
        "discovered",
        "rights_verified",
        "acquired",
        "structurally_valid",
        "scientifically_eligible",
        "protocol_ready",
        "experiment_ready",
    )


def test_summaries_skip_undiscovered_rows_but_keep_counting_later_rows():
    rows = [
        {"stratum": "C3", "status": None},
        {"stratum": "C3", "status": "acquired"},
        {"stratum": "C3", "status": "discovered"},
    ]
    table = rd.summarise(rows)
    assert table["C3"] == {
        "discovered": 2,
        "rights_verified": 1,
        "acquired": 1,
        "structurally_valid": 0,
        "scientifically_eligible": 0,
        "protocol_ready": 0,
        "experiment_ready": 0,
    }
    assert rd.summarise([{"stratum": "C9", "status": None}]) == {
        "C9": dict.fromkeys(rd.STATUSES, 0)
    }
    assert rd.ready_groups([{"stratum": "C1", "group": "a", "status": "protocol_ready"}]) == {}
    two = [
        {"stratum": "C4", "group": "b", "status": "experiment_ready"},
        {"stratum": "C4", "group": "a", "status": "experiment_ready"},
    ]
    assert rd.ready_groups(two) == {"C4": ["a", "b"]}  # sorted


def _entry(**over):
    entry = {
        "id": "e:1",
        "publisher": "pub",
        "stratum": "C5",
        "licence_class": "open",
        "eligible": True,
        "upstream_status": "verified",
        "stages": {"data_acquired": True, "structural_validation": True},
    }
    entry.update(over)
    return entry


def _declared(**over):
    declared = {
        "first_party": True,
        "independent_group": "g",
        "privacy": "handled",
        "baseline_properties": ["b"],
        "anomaly_origin": "controlled_injection",
        "units": 7,
        "min_units": 3,
        "protocol_id": "P-REL",
        "partitions": "hash",
        "view": "v",
    }
    declared.update(over)
    return declared


def test_facts_are_assembled_field_by_field():
    views = {"v": {"files": {"b.csv": {"sha256": "bb"}, "a.csv": {"sha256": "aa"}}}}
    protocols = {"P-REL": {"detection_unit": "relationship"}}
    facts = rd.facts_from(_entry(), _declared(), views, protocols)
    import hashlib

    assert facts == {
        "id": "e:1",
        "source": "pub",
        "licence_class": "open",
        "first_party": True,
        "upstream_status": "verified",
        "files_verified": True,
        "structure_passed": True,
        "independent_group": "g",
        "privacy": "handled",
        "baseline_properties": ["b"],
        "anomaly_origin": "controlled_injection",
        "units": 7,
        "min_units": 3,
        "protocol_id": "P-REL",
        "detection_unit": "relationship",
        "partitions": "hash",
        "view_sha256": hashlib.sha256(b"aabb").hexdigest(),  # files in name order
        "view_preprocessing": "research/experimental_views.py build",
        "personal_fields_remaining": [],
    }


def test_facts_without_declarations_without_stages_and_with_unknown_views_stay_empty_not_wrong():
    views = {"v": {"files": {"a": {"sha256": "aa"}}}}
    bare = {"id": "e:2", "licence_class": "open"}
    facts = rd.facts_from(bare, None, views, {})
    assert facts["first_party"] is False and facts["files_verified"] is False
    assert facts["structure_passed"] is False and facts["source"] is None
    assert facts["upstream_status"] is None and "baseline_properties" not in facts
    assert facts["view_sha256"] is None and facts["view_preprocessing"] is None
    assert facts["protocol_id"] is None and facts["detection_unit"] is None
    unknown = rd.facts_from(_entry(), _declared(view="zzz"), views, {})
    assert unknown["view_sha256"] is None
    no_protocol = rd.facts_from(_entry(), _declared(protocol_id="P-X"), views, {"P-REL": {}})
    assert no_protocol["detection_unit"] is None
    ineligible = rd.facts_from(_entry(eligible=False), _declared(), views, {})
    assert ineligible["structure_passed"] is False
    unstructured = _entry(stages={"data_acquired": True, "structural_validation": False})
    assert rd.facts_from(unstructured, _declared(), views, {})["structure_passed"] is False
    no_data = _entry(stages={"data_acquired": False, "structural_validation": True})
    assert rd.facts_from(no_data, _declared(), views, {})["files_verified"] is False


def test_main_writes_the_readiness_file_from_the_tracked_evidence(tmp_path, capsys):
    import json

    def write(name, data):
        (tmp_path / name).write_text(json.dumps(data))

    write(
        "acquired_sources.json",
        {"entries": [_entry(id="a:1", family="f"), _entry(id="a:2", stratum="C6")]},
    )
    write(
        "loghub_manifest.json", {"licence_class": "research_only", "tables": [{"id": "loghub:X"}]}
    )
    write("readiness_facts.json", {"facts": {"a:1": _declared(view="v")}})
    write("experiment_views.json", {})
    write("experimental_views.json", {"v": {"files": {"a.csv": {"sha256": "aa"}}}})
    write("anomaly_protocols.json", {"protocols": {"P-REL": {"detection_unit": "relationship"}}})
    assert rd.main(["--dir", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "readiness.json").read_text())
    by_id = {d["id"]: d for d in out["datasets"]}
    assert set(by_id) == {"a:1", "a:2", "loghub:X"}
    assert by_id["a:1"] == {
        "id": "a:1",
        "stratum": "C5",
        "group": "g",
        "status": "experiment_ready",
        "failed": None,
    }
    assert by_id["a:2"]["status"] == "structurally_valid" and by_id["a:2"]["group"] is None
    assert by_id["a:2"]["failed"]["status"] == "scientifically_eligible"
    assert by_id["loghub:X"]["stratum"] == "C4"
    assert by_id["loghub:X"]["status"] == "discovered"  # no first-party declaration here
    assert out["ready_groups"] == {"C5": ["g"]}
    assert out["summary"]["C5"]["experiment_ready"] == 1
    assert json.loads(capsys.readouterr().out) == {"C5": ["g"]}
    assert (tmp_path / "readiness.json").read_text().endswith("}\n")


def _evidence(directory, loghub_declared=True):
    import json

    def write(name, data):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(json.dumps(data))

    write("acquired_sources.json", {"entries": [_entry(id="a:1")]})
    write(
        "loghub_manifest.json", {"licence_class": "research_only", "tables": [{"id": "loghub:X"}]}
    )
    facts = {"a:1": _declared(view="v")}
    if loghub_declared:
        facts["loghub:X"] = _declared(view="v", first_party=True, protocol_id="P-REL")
    write("readiness_facts.json", {"facts": facts})
    write("experimental_views.json", {"v": {"files": {"a.csv": {"sha256": "aa"}}}})
    write("anomaly_protocols.json", {"protocols": {"P-REL": {"detection_unit": "relationship"}}})


def test_main_reads_and_writes_exactly_the_documented_files_with_stable_formatting(
    tmp_path, monkeypatch
):
    import json
    from pathlib import Path

    _evidence(tmp_path)
    read, written = [], []
    real_read, real_write = Path.read_text, Path.write_text

    def spy_read(self, *a, **k):
        read.append(self.name)
        return real_read(self, *a, **k)

    def spy_write(self, data, *a, **k):
        written.append(self.name)
        return real_write(self, data, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy_read)
    monkeypatch.setattr(Path, "write_text", spy_write)
    seen = []
    real_facts = rd.facts_from

    def spy_facts(entry, *args):
        seen.append(entry)
        return real_facts(entry, *args)

    monkeypatch.setattr(rd, "facts_from", spy_facts)
    assert rd.main(["--dir", str(tmp_path)]) == 0
    assert sorted(set(read)) == [
        "acquired_sources.json",
        "anomaly_protocols.json",
        "experimental_views.json",
        "loghub_manifest.json",
        "readiness_facts.json",
    ]
    assert written == ["readiness.json"]
    loghub = next(e for e in seen if e["id"] == "loghub:X")
    assert loghub["publisher"] == "logpai" and loghub["stratum"] == "C4"
    assert loghub["eligible"] is True
    assert loghub["stages"] == {"data_acquired": True, "structural_validation": True}
    text = (tmp_path / "readiness.json").read_text()
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    statuses = {d["id"]: d["status"] for d in json.loads(text)["datasets"]}
    assert statuses == {"a:1": "experiment_ready", "loghub:X": "experiment_ready"}


def test_main_defaults_to_the_repository_evidence_directory_and_has_a_description(
    tmp_path, monkeypatch, capsys
):
    import pytest

    fake = tmp_path / "research" / "readiness.py"
    fake.parent.mkdir()
    _evidence(tmp_path / "verification" / "evidence" / "dataset_registry_v2")
    monkeypatch.setattr(rd, "__file__", str(fake))
    from pathlib import Path

    paths = []
    real_read = Path.read_text

    def spy(self, *a, **k):
        paths.append(str(self))
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    assert rd.main([]) == 0
    monkeypatch.undo()
    base = str(tmp_path / "verification" / "evidence" / "dataset_registry_v2")
    assert paths and all(p.startswith(base + "/") for p in paths)  # exact case, not just a path
    monkeypatch.setattr(rd, "__file__", str(fake))
    assert (tmp_path / "verification/evidence/dataset_registry_v2/readiness.json").exists()
    with pytest.raises(SystemExit):
        rd.main(["--help"])
    assert "Readiness contract" in capsys.readouterr().out


def test_a_missing_view_or_protocol_name_never_matches_a_placeholder_key():
    views = {"XXXX": {"files": {"a": {"sha256": "aa"}}}}
    protocols = {"XXXX": {"detection_unit": "row"}}
    facts = rd.facts_from(_entry(), _declared(view=None, protocol_id=None), views, protocols)
    assert facts["view_sha256"] is None and facts["detection_unit"] is None
    facts = rd.facts_from(_entry(), _declared(view="", protocol_id=""), views, protocols)
    assert facts["view_sha256"] is None and facts["detection_unit"] is None
