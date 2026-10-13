from verification.refresh_profile import build_profile


def test_profile_refresh_uses_exact_coverage_and_current_revision():
    template = {
        "source_revision": "older",
        "coverage": {"line": {}, "branch": {}, "per_unit": []},
    }
    coverage = {
        "totals": {
            "covered_lines": 7,
            "num_statements": 9,
            "covered_branches": 2,
            "num_branches": 4,
        },
        "files": {
            "src/module.py": {
                "summary": {
                    "covered_lines": 7,
                    "num_statements": 9,
                    "covered_branches": 2,
                    "num_branches": 4,
                }
            }
        },
    }
    result = build_profile(template, coverage, revision="abc123", generated_at="now")
    assert result["source_revision"] == "abc123"
    assert result["coverage"]["line"] == {"covered": 7, "coverable": 9}
    assert result["coverage"]["branch"] == {"covered": 2, "coverable": 4}
    assert result["coverage"]["per_unit"][0]["unit"] == "src/module.py"
    assert template["source_revision"] == "older"
