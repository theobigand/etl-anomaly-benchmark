import pytest

from etl_benchmark.quality import Detector
from etl_benchmark.registry import DETECTOR_NAMES, all_detectors, get_detector


def test_get_detector_returns_named_instance():
    for name in DETECTOR_NAMES:
        det = get_detector(name)
        assert isinstance(det, Detector)
        assert det.name == name


def test_get_detector_unknown_raises():
    with pytest.raises(ValueError):
        get_detector("does_not_exist")


def test_all_detectors_covers_registry():
    assert {d.name for d in all_detectors()} == set(DETECTOR_NAMES)
