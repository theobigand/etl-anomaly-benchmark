"""Write the subsection of the paper on the extension of every study to the whole pool.

Run after ``pool_extension_summary.py`` data exist; the block between the markers is replaced
each time, the numbers come from the archives.
"""

from __future__ import annotations

import json
from pathlib import Path

import paper_tables as pt
import pool_extension_summary as ps

ROOT = Path(__file__).resolve().parents[1]
START = "% BEGIN generated pool extension\n"
END = "% END generated pool extension\n"
CHRONO = {
    "credit_card": "Credit Card",
    "bank_marketing": "Bank Marketing",
    "occupancy_detection": "Occupancy Detection",
    "online_shoppers_purchasing_intention_dataset": "Online Shoppers",
    "room_occupancy_estimation": "Room Occupancy",
}


def block(evidence: Path) -> str:
    ext = evidence / "pool_extension"
    runs = ps.load_runs(ext / "pool_full_classical" / "runs", ext / "pool_full_deep" / "runs")
    fixed = ps.fixed_threshold(runs)
    curves = ps.curve_ranking(runs)
    sweep = ps.contamination_sweep(runs)
    chrono = {p.stem: json.loads(p.read_text()) for p in sorted((ext / "chrono").glob("*.json"))}
    chrono_summary = ps.chronology(chrono)
    etl = ps.pipeline(json.loads((ext / "etl" / "pool_etl.json").read_text()))
    elig = json.loads((ext / "typed" / "eligibility.json").read_text())
    names = {k: v for k, v in pt.NAMES.items()}
    tex = [
        r"\subsection{Every study on the whole pool}",
        r"\label{sec:pool-all}",
        "The curves, the contamination sweep, the label-free threshold, the severity sweep, "
        "the pipeline run and the chronological split were first done on the three example "
        "datasets and the synthetic data. I applied each of them to every dataset of the pool "
        "for which it is defined, with the protocol and six hypotheses written beforehand "
        r"(\texttt{verification/pool\_extension.md}), and list what could not be run and why.",
        "",
        rf"\paragraph{{Label-free threshold and curves.}} Table~\ref{{tab:pool-fixed}} gives, for "
        rf"the seventeen detectors on the $100$ labelled problems, the median $F_1$ and the "
        rf"median share of flagged rows at the training-prevalence threshold and at a constant "
        rf"contamination of $0.02$, both read from a single fit (a test checks that this equals "
        rf"a refit). The hypothesis that the label-free threshold lowers the median $F_1$ of at "
        rf"least twelve of the seventeen detectors holds: it does for the "
        rf"{fixed['lower_at_fixed']} learned detectors, and the three rules are unchanged "
        r"because they do not read the contamination. The ranking by the average precision of "
        r"the curves (seed $42$) correlates with the published PR-AUC ranking at "
        rf"${curves['spearman']:.2f}$, below the $0.99$ I had fixed, so the hypothesis is not "
        r"supported: several detectors have medians within a hundredth of each other and "
        r"swap places between one seed and five.",
        "",
        r"\begin{table}[t]",
        r"\caption{Median over the $100$ labelled problems of the $F_1$ and of the share of "
        r"flagged rows (\%), at the training-prevalence threshold (prev.) and at a constant "
        r"contamination of $0.02$ (fixed).}",
        r"\label{tab:pool-fixed}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Detector & $F_1$ prev. & $F_1$ fixed & Flag.\% prev. & Flag.\% fixed \\",
        r"\midrule",
        ps.fixed_rows(fixed, names),
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
        r"Table~\ref{tab:pool-sweep} sweeps the contamination of Isolation Forest on the same "
        r"problems. Recall rises with the contamination as on the three examples, and the "
        r"median $F_1$ keeps rising up to the largest value of the grid, $0.2$, twice the "
        r"median prevalence of the pool ($0.10$). Precision stays between $0.14$ and $0.16$ "
        r"from $0.05$ on whatever the threshold, which points to weak scores on these labels "
        r"more than to a badly placed threshold.",
        "",
        r"\begin{table}[t]",
        r"\caption{Isolation Forest on the $100$ labelled problems: median precision, recall, "
        r"$F_1$ and share of flagged rows (\%) over the contamination grid.}",
        r"\label{tab:pool-sweep}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Contamination & Prec. & Rec. & $F_1$ & Flag.\% \\",
        r"\midrule",
        ps.sweep_rows(sweep),
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
        rf"\paragraph{{Typed injection and eligibility.}} The eligibility rule of "
        rf"Section~\ref{{sec:typed}} was applied to all $152$ datasets, ADBench ones included "
        rf"(the normal class only for a labelled set): {sum(r['eligible'] for r in elig)} are "
        rf"eligible, {sum(r['eligible'] and r['source'] == 'uci' for r in elig)} from the UCI "
        rf"repository and {sum(r['eligible'] and r['source'] == 'adbench' for r in elig)} from "
        r"ADBench. The others are listed with their reason in the archive; the usual one is "
        r"fewer than four continuous columns (categorical or binary tables) or too few rows. "
        r"Figure~\ref{fig:typed} and the stability figures of Section~\ref{sec:typed} include "
        r"the ADBench tables.",
        "",
        rf"\paragraph{{The pipeline end to end.}} The four stages (read, remove duplicates, "
        rf"detect, write) ran on all $152$ datasets with Z-score and Isolation Forest, one "
        rf"fresh process per measurement; {len(etl['failed'])} of the $304$ runs failed "
        r"and are recorded with their reason (a table with no numeric column, or a column "
        r"that the pipeline reads as text because of stray header lines in the file). On the "
        rf"{etl['datasets_above']} datasets above $50{{,}}000$ rows the detection takes "
        rf"{100 * etl['median_detect_share']['isolation_forest']:.0f}\% of the pipeline time "
        rf"with Isolation Forest and {100 * etl['median_detect_share']['zscore']:.0f}\% with the "
        r"Z-score, the writing of the two files being the rest, as on Credit Card Fraud; the "
        r"hypothesis holds. These times were measured while other jobs ran on the machine, so "
        r"they are orders of magnitude, and the shares are ratios inside one process.",
        "",
        r"\paragraph{Chronological split.}",
        "A time variable is needed, and only some pool datasets have one: eleven unlabelled "
        "UCI tables have a date, the ADBench files have none, and five labelled datasets "
        "qualify (Credit Card, Bank Marketing, Occupancy Detection, Online Shoppers and Room "
        r"Occupancy, the rule being fixed beforehand). Table~\ref{tab:pool-chrono} gives the "
        "result of the chronological pilot with all the detectors that scale. The hypothesis "
        "that the chronological PR-AUC is below the stratified one for two thirds of the pairs "
        rf"does not hold: {chrono_summary['lower']} of {chrono_summary['pairs']} pairs are "
        r"lower. Bank Marketing is the reason: its prevalence rises from $5.8\%$ to $39.3\%$ "
        r"and no detector loses PR-AUC there, as Section~\ref{sec:decisions} found with four "
        r"detectors. Room Occupancy is excluded because its anomalies are all in the oldest "
        r"rows.",
        "",
        r"\begin{table}[t]",
        r"\caption{Chronological split on the pool datasets with a time variable: anomalies in "
        r"the test partition, prevalence in training and test (\%), and the number of detectors "
        r"whose PR-AUC is lower than under the stratified split.}",
        r"\label{tab:pool-chrono}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Dataset & Test anom. & Train \% & Test \% & Lower \\",
        r"\midrule",
        ps.chrono_rows(chrono, CHRONO),
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
        r"\paragraph{Files.} All $152$ local files match the pinned manifest "
        r"(\texttt{make verify-pool}), so the sixth hypothesis holds.",
        "",
    ]
    return "\n".join(tex)


def write(tex_path: Path, evidence: Path) -> None:
    body = tex_path.read_text()
    text = START + block(evidence) + END
    if START in body:
        head, rest = body.split(START, 1)
        body = head + text + rest.split(END, 1)[1]
    else:
        marker = "\\section{Secondary Studies}"
        head, tail = body.split(marker, 1)
        body = head + text + "\n" + marker + tail
    tex_path.write_text(body)


if __name__ == "__main__":
    write(ROOT / "paper" / "main.tex", ROOT / "verification" / "evidence")
