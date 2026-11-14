"""Builders for owner-reviewed equivalence documents used by several test modules."""

from __future__ import annotations

OWNER = "the-owner"
GOVERNANCE = {"review_mode": "sole_author_owner_review", "owner": OWNER}
ENVIRONMENT = {"mutmut": "3.8.0"}


def record(key, path, source_sha256, catalog_sha256, risk="L4", **change):
    base = {
        "id": key,
        "path": path,
        "function": "compute",
        "diff": "-    return value + 1\n+    return value + 2",
        "original_behavior": "adds one",
        "mutated_behavior": "constructed example only",
        "risk": risk,
        "reason": "constructed equivalence used to exercise the arithmetic",
        "evidence": ["tests/owner_review.py"],
        "source_sha256": source_sha256,
        "catalog_sha256": catalog_sha256,
        "author": OWNER,
        "verdict": "accepted",
        "approver": OWNER,
        "decision_date": "2026-11-11",
        "policy_version": 2,
        "environment": dict(ENVIRONMENT),
        "assessments": [],
    }
    base.update(change)
    return base


def document(*records):
    return {
        "version": 2,
        "review_mode": "sole_author_owner_review",
        "owner": OWNER,
        "records": list(records),
    }
