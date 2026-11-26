"""Referential-integrity fault (T425): child rows whose reference no longer resolves.

A foreign key is declared explicitly (child columns, parent table and columns, optional type
column for a polymorphic reference); nothing is inferred from column names. The fault replaces the
reference of rows that currently resolve by a value that exists in no parent row, so the injected
rows are exactly the ones labelled faulty. References that are already unresolved in the source
(natural orphans) are measured and reported but never labelled and never touched, null references
assert nothing (SQL MATCH SIMPLE), and a polymorphic reference is resolved against the parent
its type column names, so a type without a declared parent is not an orphan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: share of the delivered child rows whose reference is broken, at low, medium and high severity
SEVERITY = (0.05, 0.2, 0.5)


@dataclass(frozen=True)
class ForeignKey:
    """``child.columns`` references ``parent.parent_columns``.

    A polymorphic reference sets ``type_column`` and maps each type value to its own
    ``(parent table, parent columns)`` in ``targets``; the other fields then name the default
    columns of the child only.
    """

    child: str
    columns: tuple[str, ...]
    parent: str = ""
    parent_columns: tuple[str, ...] = ()
    type_column: str | None = None
    targets: dict[str, tuple[str, tuple[str, ...]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type_column is None:
            if not self.parent or len(self.columns) != len(self.parent_columns):
                raise ValueError("a foreign key needs a parent with as many columns as the child")
        elif not self.targets:
            raise ValueError("a polymorphic reference needs at least one target")


def _keys(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.MultiIndex:
    return pd.MultiIndex.from_frame(frame[list(columns)])


def _resolves(
    child: pd.DataFrame,
    columns: tuple[str, ...],
    parent: pd.DataFrame,
    parent_columns: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(_keys(child, columns).isin(_keys(parent, parent_columns)))


def reference_state(
    fk: ForeignKey, tables: dict[str, pd.DataFrame], rows: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Per child row: ``asserted`` (a complete reference of a known type) and ``resolved``.

    ``rows`` is a delivered part of the child table; it defaults to the whole table.
    """
    child = tables[fk.child] if rows is None else rows
    asserted = child[list(fk.columns)].notna().all(axis=1).to_numpy().copy()
    resolved = np.zeros(len(child), dtype=bool)
    if fk.type_column is None:
        resolved = _resolves(child, fk.columns, tables[fk.parent], fk.parent_columns)
    else:
        kind = child[fk.type_column]
        asserted &= kind.isin(list(fk.targets)).to_numpy()
        for value, (parent, parent_columns) in fk.targets.items():
            hit = (kind == value).to_numpy()
            if hit.any():
                resolved[hit] = _resolves(child[hit], fk.columns, tables[parent], parent_columns)
    return pd.DataFrame({"asserted": asserted, "resolved": resolved & asserted}, index=child.index)


def natural_orphans(fk: ForeignKey, tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """References already unresolved in the source: counted, not labelled."""
    state = reference_state(fk, tables)
    return {
        "rows": len(state),
        "asserted": int(state["asserted"].sum()),
        "orphans": int((state["asserted"] & ~state["resolved"]).sum()),
    }


def orphan_share(fk: ForeignKey, tables: dict[str, pd.DataFrame], rows: pd.DataFrame) -> float:
    """Share of the asserted references of a delivered batch that do not resolve (0 if none)."""
    state = reference_state(fk, tables, rows)
    asserted = int(state["asserted"].sum())
    return float((state["asserted"] & ~state["resolved"]).sum() / asserted) if asserted else 0.0


def _absent(parent_values: pd.Series, count: int) -> list[object]:
    """Values for ``count`` rows that occur in no parent row (distinct, so also as tuples)."""
    if pd.api.types.is_numeric_dtype(parent_values) and len(parent_values):
        top = parent_values.max()
        return [top + 1 + i for i in range(count)]
    return [f"orphan-{i}" for i in range(count)]


def inject_orphans(
    fk: ForeignKey,
    tables: dict[str, pd.DataFrame],
    rows: pd.DataFrame,
    level: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, np.ndarray]:
    """The delivered child rows with some references broken, and the mask of the broken rows.

    The share is ``SEVERITY[level]`` of the delivered rows; only rows whose reference currently
    resolves can be broken. The last reference column is replaced; the source tables are not
    modified.
    """
    state = reference_state(fk, tables, rows)
    candidates = np.flatnonzero(state["resolved"].to_numpy())
    if not len(candidates):
        raise ValueError("no row has a resolvable reference to break")
    count = min(len(candidates), max(1, int(round(SEVERITY[level] * len(rows)))))
    hit = np.sort(rng.permutation(candidates)[:count])
    out = rows.copy()
    column = fk.columns[-1]
    if fk.type_column is None:
        parents = [tables[fk.parent][fk.parent_columns[-1]]]
    else:
        parents = [tables[p][cols[-1]] for p, cols in fk.targets.values()]
    values = pd.concat(parents)
    if not pd.api.types.is_numeric_dtype(values):
        out[column] = out[column].astype(object)
    out.iloc[hit, out.columns.get_loc(column)] = _absent(values, count)
    mask = np.zeros(len(rows), dtype=bool)
    mask[hit] = True
    return out, mask
