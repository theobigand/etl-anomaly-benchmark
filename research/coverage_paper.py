# ruff: noqa: E501
"""Write the paper text on dataset coverage and the v2 extensions from the archived evidence.

Two blocks between markers, replaced every time: a Results subsection and an appendix table
block. Every number is read from verification/evidence/coverage and pool_extension_v2. The prose
lives in module-level templates; ``<<name>>`` marks a value filled from the evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
START, END = "% BEGIN generated coverage v2\n", "% END generated coverage v2\n"
APP_START, APP_END = "% BEGIN generated coverage appendix\n", "% END generated coverage appendix\n"
ANCHOR = "% END generated pool extension\n"
APP_ANCHOR = "% END generated pool appendix\n"
TYPE_LABEL = {
    "missing_value": "Missing",
    "duplicate": "Dupl.",
    "univariate_outlier": "Univ.",
    "multivariate_outlier": "Multiv.",
    "distribution_shift": "Shift",
    "invalid_format": "Invalid fmt.",
    "invalid_code": "Inv. code",
    "cross_column_swap": "Swap",
}
PROTOCOL_LABEL = {
    "labelled_classical": "Labelled problems",
    "typed_injection_classical": "Typed injection, numeric protocol",
    "typed_mixed_classical": "Typed injection, mixed-schema protocol",
    "chronological": "Chronological, labelled",
    "chronological_injected_classical": "Chronological, controlled injection",
    "etl_pipeline": "End-to-end pipeline",
}
BEFORE_EXTENSIONS = 120  # tables with a detector-quality measurement before these extensions

MAIN_TEMPLATE = r"""\subsection{Coverage of the catalog and its extensions}
\label{sec:coverage-v2}
A catalog of <<datasets>> tables is not an experimental sample of <<datasets>>. I generated a coverage matrix from the archived results: a table counts as evaluated in a protocol only when a result file holds a measurement for it. The catalog comes from <<sources>> independent sources, because <<shared>> entries are ADBench and UCI versions of the same original data (the largest source, Statlog Landsat, has four entries), so the inference below takes sources as units. <<measured>> of <<datasets>> tables now have at least one detector-quality measurement, from <<measured_sources>> sources; before the extensions below, <<timing_only>> tables had only the pipeline timing run. <<retired>> table (Student Academics Performance, 131 usable rows, no labels) is retired from the active catalog and stays in the archives. The labels of the <<labelled>> labelled problems remain minority-class proxies, not data-quality faults, and the injected faults are artificial.

\begin{table}[t]
\caption{Tables by outcome in each protocol (coverage matrix). Other: not applicable (covered by another protocol), not evaluated or failed.}
\label{tab:coverage}
\centering
\footnotesize
\begin{tabular}{lrrr}
\toprule
Protocol & Executed & Unsuitable & Other \\
\midrule
<<status_rows>>
\bottomrule
\end{tabular}
\end{table}

\paragraph{Pipeline failures repaired.} The 14 failed pipeline runs of the previous subsection came from seven tables and three causes: header lines repeated inside the file (Occupancy Detection), index:value cells (Gas Sensor Array Drift), an all-missing column (Annealing), and tables with no numeric column (Mushroom, Congressional Voting Records and two student tables). The reader now removes repeated headers, parses the sparse cells, drops all-missing columns, converts date-times and encodes categories (one-hot up to twenty levels, frequency otherwise), and records each change. All $304$ runs now succeed.

\paragraph{Typed injection on mixed and small tables.} The numeric protocol excluded 94 tables. A pre-registered protocol with categorical faults (invalid code, swapped columns) and a tier for tables of 200 to 499 rows makes <<mixed_tables>> of them eligible, from <<mixed_sources>> sources; the other eight have fewer than 200 rows. The per-type detector ranking agrees with the numeric protocol on numeric-only tables (mean rank correlation $<<m1>>$, hypothesis M1 holds). Rule detectors find categorical faults less often than distance and density detectors (median recall $<<code_rules>>$ against $<<code_distance>>$ for invalid codes and $<<swap_rules>>$ against $<<swap_distance>>$ for swapped columns; M2 holds in direction, but the rules read the encoded columns, so they are not blind to categories as the protocol assumed). Small tables are not measurably different from large ones (<<holm_hits>> of <<m3_tests>> detectors differ after Holm correction; M3 holds). These results are reported beside, never pooled with, the 58 tables of the numeric protocol.

\paragraph{Chronological study with controlled injection.} Seven unlabelled UCI time series (air quality, appliances, two bike-sharing tables, home monitoring, city power and steel-industry energy) were ordered by their real timestamps, detectors were fitted on the first 60\% and faults were injected into the last 40\%, against a random split of the same rows. For the classical detectors the median false-positive difference is $<<c1>>$ (distance-based kNN and LOF reach about $+0.16$ and $+0.20$, with intervals excluding zero; C1 holds weakly), the recall difference is $<<c2>>$ and the detector ranking is nearly unchanged (rank correlation $<<c3>>$).<<deep_text>> With the four labelled tables, eleven datasets now have a real time variable, but seven of them carry artificial faults, so this strengthens the claim on the cost of temporal change, not on natural anomalies.

\paragraph{What changes and what does not.} The coverage figures change: <<measured>> tables instead of <<before>> have a detector-quality measurement, and every pipeline run now succeeds. The earlier verdicts do not change, because no new labelled problem was added: the rankings on the $100$ labelled problems, the sensitivity of the H4 ranking to the archive and the train-only replay, and hypothesis P5 on the four labelled chronological tables stand as reported. The new protocols are exploratory extensions with their own written hypotheses (M1 to M3 and C1 to C3). They add two findings: the per-type profile of the numeric protocol carries over to categorical and small tables, and fitting on the past raises the false-positive rate of distance- and reconstruction-based detectors on real time series, which the earlier chronological tables could not show without anomaly labels. Limits: the mixed-schema encoder is one choice among several, eight tables remain too small for any typed experiment, and temporal conclusions rest on seven series with artificial faults plus four labelled tables.
"""

DEEP_TEMPLATE = (
    " The six neural detectors give a median false-positive difference of "
    "$<<fpr>>$ and a rank correlation of $<<rho>>$ between the arms."
)

APPENDIX_TEMPLATE = r"""\subsection{Tables of the coverage extensions}
\label{app:coverage-tables}
\begin{table}[t]
\caption{Mixed-schema typed injection: median recall over <<sources>> independent sources, by detector and fault type.}
\label{tab:mixed-typed}
\centering
\scriptsize
\setlength{\tabcolsep}{2.5pt}
\begin{tabular}{l<<columns>>}
\toprule
Detector & <<headers>> \\
\midrule
<<rows>>
\bottomrule
\end{tabular}
\end{table}

\begin{table}[t]
\caption{Chronological minus random split, median over the seven time series: false-positive rate and mean recall of the classical detectors, with 95\% bootstrap intervals over tables.}
\label{tab:chrono-injected}
\centering
\scriptsize
\begin{tabular}{lrr}
\toprule
Detector & FPR difference & Recall difference \\
\midrule
<<chrono_rows>>
\bottomrule
\end{tabular}
\end{table}
"""


def fill(template: str, values: dict[str, Any]) -> str:
    """Replace every ``<<name>>``; a name without a value is an error, not a blank."""
    return re.sub(r"<<(\w+)>>", lambda m: str(values[m.group(1)]), template)


def _tex(text: str) -> str:
    return text.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


MATRIX = ("coverage", "coverage_matrix.json")
MIXED = ("pool_extension_v2", "typed_mixed", "summary_classical", "summary.json")
MIXED_DEEP = ("pool_extension_v2", "typed_mixed", "summary_deep", "summary.json")
CHRONO = ("pool_extension_v2", "chrono_injected", "summary_classical", "summary.json")
CHRONO_DEEP = ("pool_extension_v2", "chrono_injected", "summary_deep", "summary.json")


def facts(evidence: Path) -> dict[str, Any]:
    def load(parts: tuple[str, ...]) -> Any:
        return json.loads(evidence.joinpath(*parts).read_text())

    return {
        "matrix": load(MATRIX),
        "mixed": load(MIXED),
        "mixed_deep": load(MIXED_DEEP),
        "chrono": load(CHRONO),
        "chrono_deep": load(CHRONO_DEEP) if evidence.joinpath(*CHRONO_DEEP).exists() else None,
    }


def status_rows(by_protocol: dict[str, dict[str, int]]) -> str:
    rows = []
    for key, label in PROTOCOL_LABEL.items():
        counts = by_protocol[key]
        executed = counts.get("executed", 0)
        unsuitable = counts.get("scientifically_unsuitable", 0)
        other = sum(counts.values()) - executed - unsuitable
        rows.append(f"{label} & {executed} & {unsuitable} & {other} \\\\")
    return "\n".join(rows)


def main_block(evidence: Path) -> str:
    f = facts(evidence)
    s = f["matrix"]["summary"]
    d = f["matrix"]["diversity"]["effective_sample"]
    m, c, deep = f["mixed"], f["chrono"], f["chrono_deep"]
    rules, near = m["M2"]["invalid_code"], m["M2"]["cross_column_swap"]
    deep_text = (
        fill(
            DEEP_TEMPLATE,
            {
                "fpr": f"{deep['C1_median_detector_fpr_difference']:+.3f}",
                "rho": f"{deep['C3_mean_rank_correlation']:.2f}",
            },
        )
        if deep
        else ""
    )
    return fill(
        MAIN_TEMPLATE,
        {
            "datasets": s["datasets"],
            "sources": d["independent_sources"],
            "shared": d["entries_in_multi_entry_sources"],
            "measured": s["with_detector_quality_measurement"],
            "measured_sources": s["independent_sources_with_detector_quality_measurement"],
            "timing_only": s["datasets"] - BEFORE_EXTENSIONS,
            "retired": s["decisions"].get("retired", 0),
            "labelled": s["with_labels"],
            "before": BEFORE_EXTENSIONS,
            "status_rows": status_rows(s["by_protocol"]),
            "mixed_tables": m["datasets"],
            "mixed_sources": m["sources"],
            "m1": f"{m['M1']['mean']:.2f}",
            "code_rules": f"{rules['rules']:.2f}",
            "code_distance": f"{rules['distance_density']:.2f}",
            "swap_rules": f"{near['rules']:.2f}",
            "swap_distance": f"{near['distance_density']:.2f}",
            "holm_hits": sum(v["p_holm"] < 0.05 for v in m["M3"].values()),
            "m3_tests": len(m["M3"]),
            "c1": f"{c['C1_median_detector_fpr_difference']:+.3f}",
            "c2": f"{c['C2_median_detector_recall_difference']:+.3f}",
            "c3": f"{c['C3_mean_rank_correlation']:.2f}",
            "deep_text": deep_text,
        },
    )


def chrono_row(method: str, r: dict[str, Any]) -> str:
    fpr, rec = r["fpr_median_difference"], r["recall_median_difference"]
    return (
        f"{_tex(method)} & ${fpr:+.3f}$ [{r['fpr_ci'][0]:+.2f}, {r['fpr_ci'][1]:+.2f}] & "
        f"${rec:+.3f}$ [{r['recall_ci'][0]:+.2f}, {r['recall_ci'][1]:+.2f}] \\\\"
    )


def appendix_block(evidence: Path) -> str:
    f = facts(evidence)
    table = pd.DataFrame(f["mixed"]["medians"]).pivot(
        index="method", columns="type", values="median"
    )
    cols = [c for c in TYPE_LABEL if c in table.columns]
    rows = [
        " & ".join([_tex(m), *(f"{table.loc[m, c]:.2f}" for c in cols)]) + r" \\"
        for m in table.index
    ]
    return fill(
        APPENDIX_TEMPLATE,
        {
            "sources": f["mixed"]["sources"],
            "columns": "r" * len(cols),
            "headers": " & ".join(TYPE_LABEL[c] for c in cols),
            "rows": "\n".join(rows),
            "chrono_rows": "\n".join(chrono_row(m, r) for m, r in f["chrono"]["detectors"].items()),
        },
    )


def _insert(body: str, anchor: str, start: str, end: str, text: str) -> str:
    if start in body:
        head, rest = body.split(start, 1)
        return head + start + text + end + rest.split(end, 1)[1]
    head, tail = body.split(anchor, 1)
    return head + anchor + "\n" + start + text + end + tail


def write(tex_path: Path, evidence: Path) -> None:
    body = tex_path.read_text()
    body = _insert(body, ANCHOR, START, END, main_block(evidence))
    body = _insert(body, APP_ANCHOR, APP_START, APP_END, appendix_block(evidence))
    tex_path.write_text(body)


if __name__ == "__main__":
    write(ROOT / "paper" / "main.tex", ROOT / "verification" / "evidence")
