"""The architecture records state their facts and leave the research core untouched (#141)."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs/architecture"
RECORDS = sorted((ARCHITECTURE / "adr").glob("ADR-*.md"))
FIELDS = ("Component", "Need", "Version checked", "Licence", "Platform", "Evidence")
#: distribution names of the optional components (import names are not needed here)
PLATFORM_PACKAGES = (
    "apache-airflow", "pyspark", "duckdb", "dbt-core", "dbt-duckdb", "psycopg", "mlflow",
    "opentelemetry", "structlog", "drain3", "streamlit", "dash", "plotly",
)  # fmt: skip


def _names(requirements):
    return {
        re.split(r"[<>=!~\[; ]", r.strip(), maxsplit=1)[0].lower().replace("_", "-")
        for r in requirements
    }


def test_every_component_record_fills_each_field_with_text():
    components = [p for p in RECORDS if not p.name.startswith("ADR-0001")]
    assert len(components) >= 15
    for path in components:
        text = path.read_text()
        for field in FIELDS:
            match = re.search(rf"^\| {field} \| (.+) \|$", text, re.MULTILINE)
            assert match and len(match.group(1).strip()) >= 3, (path.name, field)
        assert "read 2026-11-26" in text and "Isolation." in text, path.name


def test_the_index_lists_every_record_exactly_once():
    index = (ARCHITECTURE / "README.md").read_text()
    for path in RECORDS:
        assert index.count(f"(adr/{path.name})") == 1, path.name
    assert len(re.findall(r"\(adr/ADR-\d{4}-", index)) == len(RECORDS)


def test_records_are_numbered_without_gaps_or_repeats():
    numbers = [int(re.match(r"ADR-(\d{4})", p.name).group(1)) for p in RECORDS]
    assert numbers == list(range(1, len(numbers) + 1))


def test_no_platform_component_is_a_research_core_dependency():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = _names(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared |= _names(extra)
    environment = (ROOT / "environment.yml").read_text().lower().replace("_", "-")
    for package in PLATFORM_PACKAGES:
        assert not any(name.startswith(package) for name in declared), package
        assert not re.search(rf"^\s*-\s*{re.escape(package)}\b", environment, re.MULTILINE), package


@pytest.mark.parametrize("name", ["airflow", "spark", "loki", "grafana", "tempo"])
def test_server_components_name_their_container_platforms_or_runtime(name):
    text = next(p for p in RECORDS if name in p.name).read_text()
    assert "linux/arm64" in text or "Java 17, 21 and 25" in text
