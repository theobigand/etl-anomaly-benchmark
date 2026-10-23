"""What the neural detectors need on top of the registry (protocol full_registry.md).

They are fitted on at most ``DEEP_FIT_CAP`` training rows, drawn at random with the seed of
the repetition, and their own seed is the seed of the repetition too. The cap is recorded in
every run that uses it.
"""

from __future__ import annotations

import pandas as pd

from etl_benchmark.registry import DEEP_NAMES, get_detector

DEEP_FIT_CAP = 20_000


def capped(train: pd.DataFrame, name: str, seed: int, cap: int = DEEP_FIT_CAP) -> pd.DataFrame:
    """The rows a detector is fitted on: all of them, or a seeded sample for a neural one."""
    if name in DEEP_NAMES and len(train) > cap:
        return train.sample(n=cap, random_state=seed)
    return train


def build(name: str, contamination: float, seed: int):
    """A registry detector; a neural one gets the seed of the repetition."""
    detector = get_detector(name, contamination)
    if name in DEEP_NAMES:
        detector.random_state = seed
    return detector
