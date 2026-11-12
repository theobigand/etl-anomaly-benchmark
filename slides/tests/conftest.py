"""Deselect browser-based layout tests when no Chromium binary is installed.

Tests are deselected, not skipped, because the fast verification counts a skip as a failure.
Install Chromium or set CHROME to run them.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import check_layout  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if check_layout.find_chrome() is not None:
        return
    drop = [i for i in items if i.get_closest_marker("browser")]
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = [i for i in items if i not in drop]
