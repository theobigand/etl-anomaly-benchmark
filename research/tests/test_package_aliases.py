"""Flat research imports and package imports must be one module object."""

import importlib
import sys


def test_a_flat_import_returns_the_package_module():
    flat = importlib.import_module("multi_schema")
    package = importlib.import_module("research.multi_schema")
    assert flat is package and sys.modules["multi_schema"] is package
    assert flat.__name__ == "research.multi_schema"


def test_names_that_are_not_research_scripts_are_not_aliased():
    assert importlib.util.find_spec("json").name == "json"
    assert "research.json" not in sys.modules
