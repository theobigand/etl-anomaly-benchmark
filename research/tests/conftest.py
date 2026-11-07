"""Import the research scripts under their package names.

The scripts import each other, and these tests import them, by flat name
(``import multi_schema``). Mutation testing identifies a function by its
module path, so a flat import hides the test from ``research.multi_schema``.
This finder serves every flat name from the package module so that one module
object exists per script and a mutant is attributed to the tests that run it.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = frozenset(path.stem for path in (ROOT / "research").glob("*.py"))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _PackageModule(importlib.abc.Loader):
    def create_module(self, spec):
        return importlib.import_module(f"research.{spec.name}")

    def exec_module(self, module):
        return None


class _FlatNames(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if path is None and fullname in NAMES:
            return importlib.util.spec_from_loader(fullname, _PackageModule())
        return None


if not any(isinstance(finder, _FlatNames) for finder in sys.meta_path):
    sys.meta_path.insert(0, _FlatNames())
