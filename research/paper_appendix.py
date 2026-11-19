"""Write the appendix of the paper that lists the full per-type matrices (all detectors).

Run after ``full_registry_summary.py``; it replaces the section between the markers each time.
"""

from __future__ import annotations

from pathlib import Path

import full_registry_summary as fs
import paper_tables as pt
import typed_summary as ts

ROOT = Path(__file__).resolve().parents[1]
START = "% BEGIN generated matrices\n"
END = "% END generated matrices\n"


def section(evidence: Path) -> str:
    out = evidence / "full_registry"
    customer = fs.synthetic_matrix(evidence, out)
    schemas = fs.schema_matrices(evidence / "multi_schema", out / "schemas_deep")
    typed = fs.merged_typed(evidence / "typed_injection" / "runs", out / "typed_deep" / "runs")
    median = fs.ordered(ts.pooled(typed)["median"])
    text = [
        r"\section{Full per-type matrices}",
        r"\label{app:matrices}",
        "The tables below give the mean recall of every detector of the registry on each "
        "injected type, over five seeds for the synthetic tables and as the median over the "
        r"$42$ real tables for the last one. The best value of each column among the detectors "
        "of the registry is in bold.",
        "",
        pt.matrix_table(
            customer, "Synthetic customer table, mean recall over five seeds.", "tab:m-customer"
        ),
        "",
        pt.matrix_table(
            schemas["transactions"].drop(index="drift", errors="ignore"),
            "Synthetic card transactions, mean recall over five seeds.",
            "tab:m-transactions",
        ),
        "",
        pt.matrix_table(
            schemas["sensors"].drop(index="drift", errors="ignore"),
            "Synthetic sensor readings, mean recall over five seeds.",
            "tab:m-sensors",
        ),
        "",
        pt.matrix_table(
            median,
            r"Typed injection into $42$ real tables, median recall over the tables.",
            "tab:m-typed",
        ),
    ]
    return "\n".join(text) + "\n"


SCHEMA_METHODS = [
    ("great_expectations", "Great Expectations"),
    ("transform_dedup", "Dedup rule"),
    ("iqr", "IQR"),
    ("isolation_forest", "Isolation Forest"),
    ("ocsvm", "One-Class SVM"),
]


def schema_rows(evidence: Path) -> str:
    """Rows of the two-schema table: mean recall of five methods on the transaction and sensor tables."""
    schemas = fs.schema_matrices(evidence / "multi_schema", evidence / "full_registry" / "schemas_deep")
    lines = []
    for schema, label in (("transactions", "Transactions"), ("sensors", "Sensors")):
        if lines:
            lines.append(r"\midrule")
        for position, (key, name) in enumerate(SCHEMA_METHODS):
            cells = " & ".join(f"{value:.2f}" for value in schemas[schema].loc[key])
            lines.append(f"{label if position == 0 else '':<12} & {name:<18} & {cells} \\\\")
    return "\n".join(lines)


def write(tex: Path, evidence: Path) -> None:
    body = tex.read_text()
    block = START + section(evidence) + END
    if START in body:
        head, rest = body.split(START, 1)
        tail = rest.split(END, 1)[1]
        body = head + block + tail
    else:
        marker = "\\bibliographystyle"
        head, tail = body.split(marker, 1)
        body = head + block + "\n" + marker + tail
    if "\\label{tab:schemas}" in body:
        body = pt.replace_body(body, "schemas", schema_rows(evidence))
    tex.write_text(body)


if __name__ == "__main__":
    write(ROOT / "paper" / "main.tex", ROOT / "verification" / "evidence")
